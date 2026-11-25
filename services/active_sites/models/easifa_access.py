"""Anonymous EasIFA credentials; no database or service-wide HTTP owner."""
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile

SESSION_HEADER = "X-Easifa-Session"
SESSION_COOKIE = "enzymind_easifa_session"
request_owner = ContextVar("enzymind_easifa_owner", default=None)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43,128}")


def valid_token(value):
    return isinstance(value, str) and bool(_TOKEN.fullmatch(value))


def configured_api_base():
    return os.getenv("ENZYMIND_EASIFA_API_BASE") or os.getenv("EASIFA_API_BASE") or None


def cookie_secure():
    return os.getenv("ENZYMIND_EASIFA_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}


def _read_key(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192:
            raise ValueError("Invalid recovery file")
        if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("Recovery file must be private to the current user")
        saved = json.load(handle)
    if (not isinstance(saved, dict) or saved.get("format") != "easifa-access"
            or saved.get("version") != 1 or not valid_token(saved.get("token"))):
        raise ValueError("Invalid recovery file")
    return saved["token"]


def _profile(api_bases):
    return hashlib.sha256("\n".join(sorted({base.rstrip('/') for base in api_bases})).encode()).hexdigest()[:20]


def load_owner_key(api_bases, *, session_key=None, session_file=None):
    """Persist a direct Python client's owner; HTTP requests supply their own owner."""
    key = session_key if session_key is not None else os.getenv("ENZYMIND_EASIFA_SESSION_KEY")
    if key is not None:
        if not valid_token(key):
            raise ValueError("Invalid ENZYMIND_EASIFA_SESSION_KEY; expected 43-128 URL-safe characters")
        return key
    filename = session_file or os.getenv("ENZYMIND_EASIFA_SESSION_FILE")
    if filename:
        path = Path(filename).expanduser()
    else:
        state = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        directory = state / "enzymind" / "easifa"
        path = directory / _profile(api_bases) / "session.json"
        # The HTTPS endpoint update must not silently orphan the old owner's jobs.
        # Reuse the existing file in place; do not copy or replace either identity.
        previous_bases = tuple(
            "http://cadd.iddd.group/easifa/api"
            if base.rstrip('/') == "https://cadd.iddd.group/easifa/api" else base
            for base in api_bases
        )
        previous_path = directory / _profile(previous_bases) / "session.json"
        if not os.path.lexists(path) and os.path.lexists(previous_path):
            path = previous_path
    try:
        return _read_key(path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        raise RuntimeError("Cannot read the EasIFA recovery file. Preserve it and check its format and permissions (0600).") from None
    temporary = None
    try:
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".session-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"format": "easifa-access", "version": 1, "token": secrets.token_urlsafe(32)}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass  # Concurrent startups must reuse the first persisted identity.
        return _read_key(path)
    except (OSError, ValueError):
        raise RuntimeError("Cannot persist the EasIFA identity. Configure a writable ENZYMIND_EASIFA_SESSION_FILE or persistent ENZYMIND_EASIFA_SESSION_KEY.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
