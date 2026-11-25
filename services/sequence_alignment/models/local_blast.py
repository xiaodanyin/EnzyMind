"""Local BLAST+ against a configured, relocatable UniProt release."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading

import requests
from urllib3.exceptions import HTTPError as TransportError

from .uniprot_client import ACCESSION, P256Adapter, uniprot_json_client
from shared.uniprot_local import LocalUniProt, LocalUniProtError
from shared.uniprot_sections import combine, ec_numbers, protein_name

SLOT = threading.BoundedSemaphore(1)


def default_database():
    return "local_uniprot" if os.getenv("ENZYMIND_BLAST_DB") else "nr"


def bundle():
    prefix = Path(os.environ["ENZYMIND_BLAST_DB"]).expanduser().resolve()
    meta = json.loads(prefix.with_name("manifest.json").read_text())
    index = json.loads(prefix.with_suffix(".pjs").read_text())
    if (prefix.name != meta["prefix"] or index["dbtype"] != "Protein"
            or index["number-of-sequences"] != meta["sequences"] or not index["files"]
            or not all(prefix.with_name(name).is_file() for name in index["files"])):
        raise ValueError("Incomplete local BLAST database")
    return prefix, meta


def binary(name):
    directory = os.getenv("ENZYMIND_BLAST_BIN_DIR")
    return str(Path(directory).expanduser().resolve() / name) if directory else name


def resolve(accession):
    """Resolve the query independently of the release used as the search space."""
    prefix, meta = bundle()
    try:
        record = LocalUniProt().fetch(accession)
    except LocalUniProtError:
        record = None
    if record:
        primary, seq, source = record
        return seq, {**source, "provider": source["name"], "resolved_accession": primary,
                     "sha256": hashlib.sha256(seq.encode("ascii")).hexdigest()}
    run = subprocess.run([binary("blastdbcmd"), "-db", prefix.name, "-entry", accession,
                          "-outfmt", "%s"], cwd=prefix.parent, capture_output=True, text=True, timeout=10)
    seq = run.stdout.strip()
    if run.returncode == 0 and re.fullmatch(r"[A-Z]+", seq):
        return seq, {"provider": meta["release"], "method": "local_snapshot", "dataset": "blast_sequence_index",
                     "requested_accession": accession,
                     "resolved_accession": accession, "sha256": hashlib.sha256(seq.encode("ascii")).hexdigest()}
    if run.returncode and "Entry not found: " + accession in run.stderr:
        return None
    raise ValueError("The BLAST index could not resolve this accession")


def _annotation_fields(doc):
    return {
        "protein_name": protein_name(doc) or "",
        "organism": doc.get("organism", {}).get("scientificName", ""),
        "ec": "; ".join(ec_numbers(doc)),
        "function": " ".join(t["value"] for c in doc.get("comments", []) if c.get("commentType") == "FUNCTION"
                             for t in c.get("texts", []) if t.get("value")),
    }


def _remote_annotations(accessions):
    # Only unresolved accessions leave the host, in one bounded request.
    with requests.Session() as client:
        client.mount("https://rest.uniprot.org/", P256Adapter())
        params = {"query": " OR ".join("accession:" + a for a in sorted(accessions)),
                  "format": "tsv", "size": len(accessions),
                  "fields": "accession,protein_name,organism_name,ec,cc_function,sequence"}
        with client.get("https://rest.uniprot.org/uniprotkb/search", params=params,
                        timeout=(3, 5), allow_redirects=False, stream=True) as response:
            response.raise_for_status()
            raw = response.raw.read(2_000_001, decode_content=True)
            if len(raw) > 2_000_000:
                raise ValueError("UniProt annotation response exceeded its limit")
    return {r["Entry"]: {"protein_name": r["Protein names"], "organism": r["Organism"],
                         "ec": r["EC number"], "function": r["Function [CC]"], "sequence": r["Sequence"]}
            for r in csv.DictReader(io.StringIO(raw.decode()), delimiter="\t") if r["Entry"] in accessions}


def annotate(hits, *, online=True):
    indexed = {}
    for hit in hits:
        accession = hit.get("accession") or ""
        if re.fullmatch(ACCESSION, accession):
            label = re.search(r"(?:sp|tr)\|" + re.escape(accession) + r"\|\S+\s+(.+)", hit.get("title", ""))
            name, _, organism = (label[1] if label else "").partition(" OS=")
            indexed[accession] = {"protein_name": name, "organism": organism}
    if not indexed:
        return "no_hits" if not hits else "unavailable"

    annotations, pending, sequences = {}, {}, {}
    for accession, identity in indexed.items():
        # The hit title supplies the index identity without another blastdbcmd process.
        try:
            record = LocalUniProt().fetch(accession, annotations=True)
        except LocalUniProtError:
            record = None
        local = json.loads(record[1]) if record else None
        primary = record[0] if record else accession
        cached = uniprot_json_client.cached_json(primary)
        doc = combine(local, cached) if local else cached or {}
        fields = _annotation_fields(doc)
        source = doc.get("enzymindSource", {})
        field_sources = {k: "local_snapshot" for k, v in _annotation_fields(local or {}).items() if v}
        for key, value in fields.items():
            if value:
                field_sources.setdefault(key, source.get("supplement", source).get("method", "uniprot_cache"))
        for key, value in identity.items():
            if value and not fields[key]:
                fields[key] = value
                field_sources[key] = "local_sequence_index"
        if field_sources:
            annotations[accession] = {**fields, "source": source.get("name", "Local UniProt sequence index"),
                                      "field_sources": field_sources}
        complete_cache = cached and (not local or source.get("supplement"))
        if not complete_cache and not all(fields.values()):
            pending.setdefault(primary, []).append(accession)
            if local:
                sequences[primary] = local["sequence"]["value"]
    if pending and online:
        try:
            rows = _remote_annotations(pending)
        except (requests.RequestException, TransportError, OSError, UnicodeError, KeyError, ValueError, csv.Error):
            rows = {}
        for primary, row in rows.items():
            if primary in sequences and sequences[primary] != row["sequence"]:
                continue
            for accession in pending.pop(primary):
                annotation = annotations.setdefault(accession, {"source": "UniProtKB", "field_sources": {}})
                for field, value in row.items():
                    if field != "sequence" and not annotation.get(field):
                        annotation[field] = value
                        if value:
                            annotation["field_sources"][field] = "uniprot_api"
                if "uniprot_api" in annotation["field_sources"].values() and annotation["source"] != "UniProtKB":
                    annotation["source"] += " + UniProt API"
    for hit in hits:
        if hit.get("accession") in annotations:
            hit["annotation"] = annotations[hit["accession"]]
    if not pending and all(h.get("annotation") for h in hits):
        return "complete"
    if annotations:
        return "partial"
    return "unavailable" if online else "disabled"



def search(sequence, maximum, evalue, parse):
    if not os.getenv("ENZYMIND_BLAST_DB"):
        return {"success": False, "error_code": "blast_unavailable", "error": "Local UniProt BLAST is disabled."}
    if len(sequence) > 10000 or not 1 <= maximum <= 50:
        return {"success": False, "error_code": "invalid_input", "error": "Submit up to 10,000 residues and 1–50 hits."}
    if not SLOT.acquire(blocking=False):
        return {"success": False, "error_code": "blast_busy", "error": "A local alignment is running. Try again shortly."}
    try:
        prefix, meta = bundle()
        threads = max(1, int(os.getenv("ENZYMIND_BLAST_THREADS", "4")))
        timeout = max(1, int(os.getenv("ENZYMIND_BLAST_TIMEOUT", "120")))
        command = [binary("blastp"), "-db", prefix.name, "-query", "-", "-outfmt", "5",
                   "-num_threads", str(threads), "-max_target_seqs", str(maximum),
                   "-max_hsps", "1", "-evalue", str(evalue)]
        run = subprocess.run(command, cwd=prefix.parent, input=f">query\n{sequence}\n",
                             capture_output=True, text=True, timeout=timeout)
        if run.returncode:
            raise OSError("blastp failed")
        result = parse(run.stdout, None, maximum, evalue, "local_uniprot", len(sequence))
        for hit in result["alignments"]:
            match = re.search(r"(?:sp|tr)\|(" + ACCESSION + r")\|", hit["title"])
            if match:
                hit["accession"] = match.group(1)
        result.update(source="Local NCBI BLAST+", database_release=meta["release"],
                      database_size=meta["sequences"])
        result["annotation_status"] = annotate(
            result["alignments"], online=os.getenv("ENZYMIND_BLAST_ANNOTATE", "true").lower() == "true")
        return result
    except subprocess.TimeoutExpired:
        return {"success": False, "error_code": "blast_timeout", "error": "Local BLAST exceeded its time limit."}
    except (OSError, ValueError, KeyError):
        return {"success": False, "error_code": "blast_unavailable", "error": "Check the local BLAST executable and database bundle."}
    finally:
        SLOT.release()
