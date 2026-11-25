"""Shared, dependency-free bounds. All names are logical names, never host paths."""
import base64
import io
import json
import re
import tarfile
from pathlib import PurePosixPath

CODE_BYTES = 64 * 1024
OUTPUT_BYTES = 128 * 1024
FILE_BYTES = 2 * 1024 * 1024
FILES_BYTES = 5 * 1024 * 1024
FILE_COUNT = 10
INPUT_BYTES = 6 * 1024 * 1024
ARCHIVE_BYTES = 16 * 1024 * 1024
MIME = {'.json': 'application/json', '.csv': 'text/csv', '.txt': 'text/plain', '.png': 'image/png'}
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\.(json|csv|txt|png)')


class Rejected(ValueError):
    pass


def json_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Rejected('invalid_json') from exc


def strict_json(raw):
    try:
        return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Rejected('invalid_json') from exc


def validate_code(code):
    try:
        valid = isinstance(code, str) and bool(code.strip()) and len(code.encode('utf-8')) <= CODE_BYTES
    except UnicodeError:
        valid = False
    if not valid:
        raise Rejected('Code must contain 1–65536 UTF-8 bytes.')


def validate_files(files):
    if not isinstance(files, list) or len(files) > FILE_COUNT:
        raise Rejected('file_count')
    total, names, decoded = 0, set(), []
    for item in files:
        if not isinstance(item, dict) or set(item) != {'name', 'content'}:
            raise Rejected('file_schema')
        name = item['name']
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise Rejected('file_name')
        names.add(name)
        try:
            raw = base64.b64decode(item['content'], validate=True)
        except (ValueError, TypeError) as exc:
            raise Rejected('file_encoding') from exc
        total += len(raw)
        if len(raw) > FILE_BYTES or total > FILES_BYTES:
            raise Rejected('file_size')
        suffix = PurePosixPath(name).suffix
        if suffix == '.png':
            # Never serve arbitrary bytes under an image content type.
            if len(raw) < 24 or raw[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
                raise Rejected('invalid_png')
            w, h = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
            if not w or not h or w * h > 16_000_000:
                raise Rejected('png_dimensions')
        else:
            try:
                raw.decode('utf-8')
            except UnicodeError as exc:
                raise Rejected('invalid_text') from exc
            if suffix == '.json':
                strict_json(raw)
        decoded.append((name, MIME[suffix], raw))
    return decoded


def input_archive(code, inputs, files):
    validate_code(code)
    data = json_bytes(inputs)
    decoded = validate_files(files)
    if len(data) + sum(len(raw) for _, _, raw in decoded) > INPUT_BYTES:
        raise Rejected('input_size')
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        entries = [('code.py', code.encode()), ('input.json', data)]
        entries += [('inputs/' + name, raw) for name, _, raw in decoded]
        for name in ('inputs', 'output'):
            entry = tarfile.TarInfo(name)
            entry.type, entry.mode, entry.uid, entry.gid = tarfile.DIRTYPE, 0o700, 10001, 10001
            archive.addfile(entry)
        for name, raw in entries:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.uid, entry.gid = len(raw), 0o600, 10001, 10001
            archive.addfile(entry, io.BytesIO(raw))
    return stream.getvalue()


def output_archive(raw):
    """Inspect the *whole* frozen writable filesystem, never extract to disk.

    Including scratch/inputs catches hard links to files outside output, too.
    All writable regular files live on /work (other mounts are separate devices).
    """
    if len(raw) > ARCHIVE_BYTES:
        raise Rejected('snapshot_size')
    files, value, names, count = [], None, set(), 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            for member in archive:
                count += 1
                path = PurePosixPath(member.name)
                if (count > 1024 or member.name in names or path.is_absolute() or
                        member.size < 0 or member.name.rstrip('/') != str(path) or
                        '..' in path.parts or not path.parts or path.parts[0] != 'work' or
                        member.linkname or member.sparse is not None or
                        any(k.startswith('GNU.sparse') for k in member.pax_headers) or
                        not (member.isfile() or member.isdir())):
                    raise Rejected('unsafe_archive')
                names.add(member.name)
                if member.isdir():
                    if path.parts[:2] == ('work', 'output') and len(path.parts) > 2:
                        raise Rejected('flat_output_required')
                    continue
                if path.parts[:2] == ('work', 'output'):
                    if len(path.parts) != 3 or not NAME.fullmatch(path.name) or member.size > FILE_BYTES:
                        raise Rejected('output_file')
                    files.append({'name': path.name, 'content': base64.b64encode(archive.extractfile(member).read()).decode()})
                    if len(files) > FILE_COUNT:
                        raise Rejected('file_count')
                elif member.name == 'work/result.json':
                    if member.size > OUTPUT_BYTES:
                        raise Rejected('json_size')
                    value = strict_json(archive.extractfile(member).read())
    except (tarfile.TarError, OSError) as exc:
        raise Rejected('invalid_archive') from exc
    validate_files(files)
    return value, files
