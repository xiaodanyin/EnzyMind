"""Pack or install a versioned UniProt BLAST database using tar and zstd."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(directory):
    metadata = json.loads((directory / "manifest.json").read_text())
    prefix = metadata["prefix"]
    if prefix != "uniprot" or metadata["sequences"] <= 0:
        raise ValueError("Invalid release manifest")
    index = json.loads((directory / "uniprot.pjs").read_text())
    if (metadata["sequences"] != index["number-of-sequences"] or index["dbtype"] != "Protein"
            or metadata["residues"] != index["number-of-letters"] or not index["files"]):
        raise ValueError("BLAST index does not match its manifest")
    checked = set()
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([\w.-]+)", line)
        if not match:
            raise ValueError("Invalid checksum entry")
        digest, name = match.groups()
        if name in {".", "..", "SHA256SUMS"} or name in checked:
            raise ValueError("Invalid checksum filename")
        path = directory / name
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise ValueError("Checksum mismatch: " + name)
        checked.add(name)
    required = {"manifest.json", "uniprot.pjs", *index["files"]}
    if not required <= checked or checked | {"SHA256SUMS"} != {p.name for p in directory.iterdir()}:
        raise ValueError("Incomplete or unexpected release contents")
    return directory / prefix


def pack(directory, output_dir):
    verify(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / (directory.name + ".tar.zst")
    checksum = archive.with_suffix(".zst.sha256")
    if archive.exists() or checksum.exists():
        raise FileExistsError(archive)
    with tempfile.TemporaryDirectory(dir=output_dir) as work:
        temp = Path(work) / archive.name
        subprocess.run(["tar", "-I", "zstd -T2 -5", "-cf", str(temp.resolve()), "-C",
                        str(directory.resolve().parent), "--", directory.name], check=True)
        sums = temp.with_suffix(".zst.sha256")
        sums.write_text(f"{sha256(temp)}  {archive.name}\n")
        os.link(temp, archive)
        os.link(sums, checksum)
    print(archive)


def install(archive, root):
    if not archive.name.endswith(".tar.zst"):
        raise ValueError("Expected a .tar.zst release")
    version = archive.name[:-len(".tar.zst")]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise ValueError("Invalid release name")
    expected = archive.with_suffix(".zst.sha256").read_text().rstrip("\n")
    if expected != f"{sha256(archive)}  {archive.name}":
        raise ValueError("Archive checksum mismatch")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / version
    with tempfile.TemporaryDirectory(dir=root) as work:
        stage = Path(work) / version
        stage.mkdir()
        with subprocess.Popen(["zstd", "-dc", "--", str(archive)], stdout=subprocess.PIPE) as decoder:
            try:
                with tarfile.open(fileobj=decoder.stdout, mode="r|") as files:
                    for member in files:
                        path = PurePosixPath(member.name)
                        if path.parts == (version,) and member.isdir():
                            continue
                        if (len(path.parts) != 2 or path.parts[0] != version or path.name in {".", ".."}
                                or not member.isfile() or not re.fullmatch(r"[\w.-]+", path.name)):
                            raise ValueError("Unexpected archive member")
                        with (stage / path.name).open("xb") as out, files.extractfile(member) as data:
                            shutil.copyfileobj(data, out)
                # tarfile may stop before the compressor's final zero blocks.
                while decoder.stdout.read(65536):
                    pass
            finally:
                decoder.stdout.close()
            if decoder.wait():
                raise ValueError("Corrupt compressed archive")
        prefix = verify(stage)
        configured_bins = os.getenv("ENZYMIND_BLAST_BIN_DIR")
        bin_dir = Path(configured_bins).expanduser().resolve() if configured_bins else Path()
        subprocess.run([str(bin_dir / "blastp"), "-version"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(bin_dir / "blastdbcmd"), "-db", prefix.name, "-info"], cwd=stage,
                       check=True, stdout=subprocess.DEVNULL)
        if destination.exists():
            verify(destination)
            if (stage / "SHA256SUMS").read_bytes() != (destination / "SHA256SUMS").read_bytes():
                raise ValueError("A different database already uses this release name")
        else:
            stage.rename(destination)
    print(f"ENZYMIND_BLAST_DB={destination.resolve() / 'uniprot'}")


if __name__ == "__main__":
    arg = argparse.ArgumentParser(description=__doc__)
    commands = arg.add_subparsers(dest="command", required=True)
    p = commands.add_parser("pack")
    p.add_argument("directory", type=Path)
    p.add_argument("output_dir", type=Path)
    p = commands.add_parser("install")
    p.add_argument("archive", type=Path)
    p.add_argument("root", type=Path)
    args = arg.parse_args()
    if args.command == "pack":
        pack(args.directory, args.output_dir)
    else:
        install(args.archive, args.root)
