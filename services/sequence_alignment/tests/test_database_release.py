import shutil

import pytest

from deploy.build_database import build
from deploy.release import install, pack
from models.blast_searcher import BlastSearcher


@pytest.mark.skipif(any(shutil.which(tool) is None for tool in ("blastp", "blastdbcmd", "makeblastdb", "tar", "zstd")),
                    reason="Integration test requires NCBI BLAST+, tar and zstd")
def test_release_moves_between_roots_with_spaces(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.fasta"
    sequence = "MTKHGDNFICVRYELEPQWVASNKTLHDIMYRWCQFGPAS"
    source.write_text(">sp|P01308|TEST Synthetic software test record\n" + sequence + "\n")
    version = "reviewed-test"
    build_dir = tmp_path / "build copy" / version
    build(source, build_dir, "software test")
    transfer = tmp_path / "transfer"
    pack(build_dir, transfer)
    target = tmp_path / "installed releases"
    archive = transfer / (version + ".tar.zst")
    install(archive, target)
    install(archive, target)
    monkeypatch.setenv("ENZYMIND_BLAST_DB", str(target / version / "uniprot"))
    monkeypatch.setenv("ENZYMIND_BLAST_ANNOTATE", "false")
    hit = BlastSearcher().search_from_input("P01308", database="local_uniprot")
    assert hit["status"] == "completed" and hit["query_length"] == len(sequence)
    assert hit["alignments"][0]["query"] == sequence


def test_invalid_incoming_archive_is_never_published(tmp_path):
    archive = tmp_path / "test.tar.zst"
    archive.write_bytes(b"invalid synthetic test input")
    archive.with_suffix(".zst.sha256").write_text("0" * 64 + "  test.tar.zst\n")
    with pytest.raises(ValueError, match="Archive checksum mismatch"):
        install(archive, tmp_path / "unpublished")
    assert not (tmp_path / "unpublished").exists()
