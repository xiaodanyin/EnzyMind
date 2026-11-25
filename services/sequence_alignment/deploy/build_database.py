"""Build a relocatable protein BLAST database from a UniProt FASTA export."""
import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def build(source, destination, release):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    opener = gzip.open if source.suffix == ".gz" else open
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage = Path(temp)
        bundle = stage / "database"
        bundle.mkdir()
        fasta = stage / "input.fasta"
        count = 0
        residue_digest = hashlib.sha256()
        digest = hashlib.sha256()
        with opener(source, "rb") as reader, fasta.open("wb") as writer:
            for line in reader:
                if line.startswith(b">"):
                    count += 1
                    residue_digest.update(b">")
                else:
                    residue_digest.update(line.strip().upper())
                digest.update(line)
                writer.write(line)
        # makeblastdb 2.16 parses spaces in its output prefix even within one argv
        # element. Keep the large files on the destination volume, using a short alias.
        with tempfile.TemporaryDirectory(dir="/tmp") as aliases:
            (Path(aliases) / "stage").symlink_to(stage.resolve(), target_is_directory=True)
            subprocess.run(["makeblastdb", "-dbtype", "prot", "-blastdb_version", "5", "-parse_seqids",
                            "-in", "stage/input.fasta", "-title", release, "-out", "stage/database/uniprot"],
                           cwd=aliases, check=True)
        # Read every indexed sequence back, including its boundary, before publishing.
        decoded = hashlib.sha256()
        with subprocess.Popen(["blastdbcmd", "-db", "uniprot", "-entry", "all", "-outfmt", "%s"],
                              cwd=bundle, stdout=subprocess.PIPE) as check:
            for sequence in check.stdout:
                decoded.update(b">" + sequence.strip())
            if check.wait() or decoded.digest() != residue_digest.digest():
                raise ValueError("Indexed sequence content differs from the source FASTA")
        metadata = json.loads((bundle / "uniprot.pjs").read_text())
        if metadata["number-of-sequences"] != count or not count:
            raise ValueError("Indexed count does not match the source FASTA")
        manifest = {"release": release, "prefix": "uniprot", "sequences": count,
                    "residues": metadata["number-of-letters"], "fasta_sha256": digest.hexdigest(),
                    "tool": subprocess.check_output(["makeblastdb", "-version"], text=True).splitlines()[0]}
        (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        with (bundle / "SHA256SUMS").open("x") as checks:
            for path in sorted(bundle.iterdir()):
                if path.name != "SHA256SUMS":
                    with path.open("rb") as data:
                        checks.write(f"{hashlib.file_digest(data, 'sha256').hexdigest()}  {path.name}\n")
        bundle.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fasta", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--release", required=True)
    args = parser.parse_args()
    build(args.fasta, args.destination, args.release)
