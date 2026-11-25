"""Write reviewed entries from an EasIFA v1 snapshot to gzip FASTA on stdout."""
import argparse
import gzip
import json
import sqlite3
import sys
from pathlib import Path


def export(path, output):
    expected = json.loads(path.with_name("manifest.json").read_text())["reviewed_count"]
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        # EasIFA v1 builds the name directory in source order (Swiss-Prot first).
        # Verify uniqueness, actual reviewed flags, and the published count.
        ids = sorted({r[0] for r in db.execute(
            "SELECT c0 FROM uniprot_name_fts_content ORDER BY id LIMIT ?", (expected,))})
        if len(ids) != expected:
            raise ValueError("Snapshot directory does not match its manifest")
        with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=2, mtime=0) as out:
            for accession in ids:
                row = db.execute("SELECT sequence_value,protein_name,organism_name FROM uniprot_entry "
                                 "WHERE primary_accession=? AND reviewed=1", (accession,)).fetchone()
                if row is None:
                    raise ValueError("Snapshot directory is not ordered by reviewed status")
                sequence, name, organism = row
                title = " ".join((name or "").split())
                if organism:
                    title += " OS=" + " ".join(organism.split())
                out.write(f">sp|{accession}|{accession} {title}\n{sequence}\n".encode())
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    export(parser.parse_args().snapshot, sys.stdout.buffer)
