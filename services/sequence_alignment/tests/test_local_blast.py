from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from urllib3.exceptions import ProtocolError

from main import app
from models import local_blast


def test_broken_local_index_fails_without_external_lookup(monkeypatch, tmp_path):
    monkeypatch.setenv("ENZYMIND_BLAST_DB", str(tmp_path / "missing-index"))
    with patch("models.blast_searcher.uniprot_client.fetch") as fetch:
        result = TestClient(app).post("/api/query/blast", json={"query": "P01308"})
    assert result.status_code == 503
    assert result.json()["error_code"] == "blast_unavailable"
    fetch.assert_not_called()


def test_lookup_distinguishes_miss_from_broken_index(tmp_path):
    with patch.object(local_blast, "bundle", return_value=(tmp_path / "index", {})), \
         patch.object(local_blast.subprocess, "run", return_value=CompletedProcess([], 1, "", "Entry not found: P01308")):
        assert local_blast.resolve("P01308") is None


def test_interrupted_annotation_preserves_local_alignment():
    session = MagicMock()
    response = session.return_value.__enter__.return_value.get.return_value.__enter__.return_value
    response.raw.read.side_effect = ProtocolError("stream interrupted")
    run = CompletedProcess([], 0, "XML", "")
    hits = [{"title": "sp|P01308|INS_HUMAN Insulin"}]
    with patch.dict("os.environ", {"ENZYMIND_BLAST_DB": "/installed/uniprot", "ENZYMIND_BLAST_ANNOTATE": "true"}), \
         patch.object(local_blast, "bundle", return_value=(Path("/installed/uniprot"), {"release": "test", "sequences": 1})), \
         patch.object(local_blast.subprocess, "run", return_value=run), \
         patch.object(local_blast.requests, "Session", session):
        data = local_blast.search("MAAAA", 3, 0.01, lambda *args: {"success": True, "alignments": hits})
    assert data["success"] and data["annotation_status"] == "partial"
    assert data["alignments"][0]["annotation"]["protein_name"] == "Insulin"
    assert data["alignments"][0]["accession"] == "P01308"


def test_cached_and_local_fields_limit_the_batch_to_unresolved_entries():
    import json
    local = {"primaryAccession": "P00330", "sequence": {"value": "MAA"},
             "enzymindSource": {"name": "Snapshot", "method": "local_snapshot", "annotation_scope": ["sequence"]},
             "enzymindEcNumbers": ["1.1.1.1"]}
    cached = {"primaryAccession": "P00761", "sequence": {"value": "MAA"},
              "enzymindSource": {"name": "Cached UniProt", "method": "uniprot_cache"}}
    hits = [{"accession": a, "title": f"sp|{a}|ENTRY Indexed name OS=Indexed organism"} for a in ("P00330", "P00761")]
    row = {"sequence": "MAA", "organism": "Remote species", "protein_name": "Remote name",
           "ec": "9.9.9.9", "function": "Supplemental function"}
    def supplement(ids):
        assert set(ids) == {"P00330"}
        return {"P00330": row}

    with patch.object(local_blast.LocalUniProt, "fetch", side_effect=lambda a, **kw: ("P00330", json.dumps(local), {}) if a == "P00330" else None), \
         patch.object(local_blast.uniprot_json_client, "cached_json", side_effect=lambda a: cached if a == "P00761" else None), \
         patch.object(local_blast, "_remote_annotations", side_effect=supplement) as remote:
        assert local_blast.annotate(hits, online=False) == "partial"
        remote.assert_not_called()
        assert local_blast.annotate(hits) == "complete"
        assert remote.call_count == 1
        assert hits[0]["annotation"]["ec"] == "1.1.1.1"
        assert hits[0]["annotation"]["function"] == "Supplemental function"
        assert hits[0]["annotation"]["organism"] == "Indexed organism"
        assert "function" not in hits[1]["annotation"]["field_sources"]
        row["sequence"] = "MTA"
        assert local_blast.annotate(hits) == "partial"
        assert not hits[0]["annotation"]["function"]
