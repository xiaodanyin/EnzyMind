"""Durable owner-scoped conversations, turns, tool events and scientific results.

The browser holds a random capability; only its digest is persisted. A separate,
short-lived turn capability authorizes n8n tools. Neither is returned in results.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
import math
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from .result_catalog import TOOLS, compact, payload_error
from .retention_policy import expiry_fields
from . import agent_quota
from .sequence_data import normalize_active_site_payload


def uid():
    return str(uuid.uuid4())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def estimate_tokens(value):
    """Conservative, Unicode-aware estimate, not a model tokenizer."""
    return math.ceil(sum(1 / 3 if ord(c) < 128 else 2 for c in value))


class WorkspaceStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("ENZYMIND_WORKSPACE_DB", str(
            Path(__file__).resolve().parents[1] / "files/workspace/workspace.sqlite3")))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            if not db.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchone():
                db.execute('PRAGMA auto_vacuum=INCREMENTAL')
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                  created REAL NOT NULL, updated REAL NOT NULL,
                  summary TEXT NOT NULL DEFAULT '', summarized_count INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS sessions_owner ON sessions(owner, updated);
                CREATE TABLE IF NOT EXISTS turns (
                  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, owner TEXT NOT NULL,
                  request_id TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL,
                  refs TEXT NOT NULL, output TEXT NOT NULL DEFAULT '', error TEXT,
                  token_hash TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                  UNIQUE(owner, request_id));
                CREATE UNIQUE INDEX IF NOT EXISTS active_session ON turns(session_id)
                  WHERE status IN ('queued','running');
                CREATE TABLE IF NOT EXISTS events (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT NOT NULL,
                  kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS events_turn ON events(turn_id, seq);
                CREATE TABLE IF NOT EXISTS results (
                  id TEXT PRIMARY KEY, owner TEXT NOT NULL, session_id TEXT, turn_id TEXT,
                  tool TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
                  inputs TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL,
                  duration REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS results_owner ON results(owner, created);
                CREATE INDEX IF NOT EXISTS results_created ON results(created);
                CREATE INDEX IF NOT EXISTS results_tool_status_created ON results(tool,status,created);
                CREATE INDEX IF NOT EXISTS turns_created ON turns(created);
                CREATE INDEX IF NOT EXISTS turns_session_created ON turns(session_id, created);
                CREATE INDEX IF NOT EXISTS events_created ON events(created);
                CREATE TABLE IF NOT EXISTS maintenance (
                  name TEXT PRIMARY KEY, updated REAL NOT NULL, report TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_usage (
                  turn_id TEXT PRIMARY KEY, owner TEXT NOT NULL, quota_date TEXT NOT NULL,
                  state TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS agent_usage_owner_day ON agent_usage(owner, quota_date);
                CREATE INDEX IF NOT EXISTS agent_usage_created ON agent_usage(created);
            """)
            # Additive migrations preserve existing conversations and result IDs.
            from .python_sandbox import init_schema
            init_schema(db)
            db.execute("BEGIN IMMEDIATE")
            for table, additions in {
                "sessions": {"memory_revision": "INTEGER NOT NULL DEFAULT 0", "compression_count": "INTEGER NOT NULL DEFAULT 0", "context_tokens": "INTEGER NOT NULL DEFAULT 0", "retention_reset_at": "REAL NOT NULL DEFAULT 0"},
                "turns": {"lease_expires": "REAL NOT NULL DEFAULT 0", "partial_output": "TEXT NOT NULL DEFAULT ''", "billing_mode": "TEXT NOT NULL DEFAULT 'legacy'", "source_ip_hash": "TEXT NOT NULL DEFAULT ''"},
            }.items():
                columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
                for name, definition in additions.items():
                    if name not in columns:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def session(self, owner, session_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=? AND owner=?", (session_id, owner)).fetchone()
        if row is None:
            raise HTTPException(404, "Conversation not found in this workspace. Records are automatically removed after 90 days.")
        return dict(row)

    def create_session(self, owner, title="New research conversation"):
        session_id, now = uid(), time.time()
        with self.db() as db:
            db.execute("INSERT INTO sessions(id,owner,title,created,updated) VALUES(?,?,?,?,?)",
                       (session_id, owner, title[:120], now, now))
        return self.session(owner, session_id)

    def sessions(self, owner):
        with self.db() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,title,created,updated FROM sessions WHERE owner=? ORDER BY updated DESC LIMIT 100", (owner,))]

    def turns(self, owner, session_id):
        self.session(owner, session_id)
        with self.db() as db:
            rows = db.execute("SELECT id FROM turns WHERE owner=? AND session_id=? ORDER BY created", (owner, session_id)).fetchall()
        return [self.turn(owner, r["id"]) for r in rows]

    def turn(self, owner, turn_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM turns WHERE id=? AND owner=?", (turn_id, owner)).fetchone()
            events = db.execute("SELECT seq,kind,data,created FROM events WHERE turn_id=? ORDER BY seq", (turn_id,)).fetchall() if row else []
        if not row:
            raise HTTPException(404, "Turn not found in this workspace.")
        turn = dict(row)
        turn.pop("token_hash")
        turn.pop("source_ip_hash", None)
        turn.pop("owner")
        turn["references"] = json.loads(turn.pop("refs"))
        turn["events"] = [{**dict(e), "data": json.loads(e["data"])} for e in events]
        turn.update(expiry_fields(turn['created']))
        return turn

    def usage(self, owner):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            agent_quota.reconcile(db)
            return agent_quota.usage(db, owner)

    def begin(self, owner, session_id, request_id, message, refs, billing_mode='free', source_ip_hash=''):
        if billing_mode not in ('free', 'byok'):
            raise ValueError('Invalid billing mode.')
        self.recover()
        self.session(owner, session_id)
        now, turn_id, token = time.time(), uid(), secrets.token_urlsafe(36)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            # Serialize attachment validation with retention deletion.
            for result_id in refs:
                self.result(owner, result_id)
            prior = db.execute("SELECT id,session_id,message,refs FROM turns WHERE owner=? AND request_id=?", (owner, request_id)).fetchone()
            if prior:
                if (prior["session_id"], prior["message"], json.loads(prior["refs"])) != (session_id, message, refs):
                    raise HTTPException(409, "This request ID was already used for different input.")
                return self.turn(owner, prior["id"]), None
            try:
                db.execute("INSERT INTO turns(id,session_id,owner,request_id,status,message,refs,token_hash,created,updated,lease_expires,billing_mode,source_ip_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (turn_id, session_id, owner, request_id, "queued", message, json.dumps(refs), digest(token), now, now, now + 180, billing_mode, source_ip_hash))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "This conversation has a running turn. Wait or stop it before sending another.")
            if billing_mode == 'free':
                agent_quota.reserve(db, owner, turn_id, now)
            db.execute("UPDATE sessions SET updated=?,title=CASE WHEN title='New research conversation' THEN ? ELSE title END WHERE id=?",
                       (now, message[:80], session_id))
        return self.turn(owner, turn_id), token

    def authorize_turn(self, token):
        with self.db() as db:
            row = db.execute("SELECT * FROM turns WHERE token_hash=? AND status='running' AND created>? AND lease_expires>?",
                             (digest(token), time.time() - 7200, time.time())).fetchone()
        if not row:
            raise HTTPException(403, "The tool execution capability is expired or invalid.")
        return dict(row)

    def event(self, turn_id, kind, data):
        with self.db() as db:
            db.execute("INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)",
                       (turn_id, kind, json.dumps(data, ensure_ascii=False), time.time()))

    def status(self, owner, turn_id, status, output="", error=None):
        with self.db() as db:
            db.execute("UPDATE turns SET status=?,output=?,error=?,updated=? WHERE id=? AND owner=? AND status IN ('queued','running')",
                       (status, output, error, time.time(), turn_id, owner))
            agent_quota.reconcile(db)

    def append_partial(self, owner, turn_id, text):
        """Checkpoint visible text without committing an answer or memory."""
        now = time.time()
        with self.db() as db:
            return db.execute("UPDATE turns SET partial_output=partial_output||?,updated=? WHERE id=? AND owner=? AND status='running' AND lease_expires>? AND created>? AND length(partial_output)+length(?)<=262144",
                              (text, now, turn_id, owner, now, now - 7200, text)).rowcount == 1

    def memory(self, owner, session_id, summary, summarized_count):
        # Administrative/backward-compatible writer. In-flight answers use complete().
        with self.db() as db:
            db.execute("UPDATE sessions SET summary=?,summarized_count=?,updated=?,memory_revision=memory_revision+1 WHERE id=? AND owner=?",
                       (summary, summarized_count, time.time(), session_id, owner))

    def renew(self, owner, turn_id):
        now = time.time()
        with self.db() as db:
            return db.execute("UPDATE turns SET lease_expires=MIN(?,created+7200),updated=? WHERE id=? AND owner=? AND status IN ('queued','running') AND lease_expires>? AND created>?",
                              (now + 180, now, turn_id, owner, now, now - 7200)).rowcount == 1

    def complete(self, owner, turn_id, revision, output, summary, count, references, compression_count=0, context_tokens=0):
        """Commit reply, citations and memory together, only for the live worker."""
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            turn = db.execute("SELECT * FROM turns WHERE id=? AND owner=?", (turn_id, owner)).fetchone()
            if not turn or turn['status'] != 'running' or turn['lease_expires'] <= now or turn['created'] + 7200 <= now:
                raise ValueError("This turn no longer holds its execution lease. Saved results are preserved.")
            session = db.execute("SELECT * FROM sessions WHERE id=? AND owner=?", (turn['session_id'], owner)).fetchone()
            history_count = db.execute("SELECT COUNT(*)*2 FROM turns WHERE session_id=? AND status='completed'", (turn['session_id'],)).fetchone()[0]
            if session['memory_revision'] != revision:
                raise ValueError("Conversation memory changed while this answer was running. Saved results are preserved.")
            if (not isinstance(summary, str) or type(count) is not int or count % 2 or
                    not session['summarized_count'] <= count <= history_count or
                    (count > session['summarized_count'] and (not summary.strip() or estimate_tokens(summary) > 1600)) or
                    (count == session['summarized_count'] and summary != session['summary'])):
                raise ValueError("Invalid memory update. The original conversation is preserved.")
            if not isinstance(output, str) or not output.strip():
                raise ValueError("Empty answer; memory was not changed.")
            if type(compression_count) is not int or not 0 <= compression_count <= 100 or type(context_tokens) is not int or not 0 <= context_tokens <= 2_000_000:
                raise ValueError("Invalid memory budget metadata.")
            db.execute("UPDATE sessions SET summary=?,summarized_count=?,memory_revision=memory_revision+1,compression_count=compression_count+?,context_tokens=?,updated=? WHERE id=?",
                       (summary, count, compression_count, context_tokens, now, turn['session_id']))
            db.execute("UPDATE turns SET status='completed',output=?,partial_output='',error=NULL,updated=? WHERE id=?", (output, now, turn_id))
            agent_quota.reconcile(db, now)
            db.execute("INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)", (turn_id, 'memory', json.dumps({'state':'saved','label':'Answer and memory saved','summarized_count':count,'context_tokens':context_tokens,'compression_count':compression_count}), now))
            db.execute("INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)", (turn_id, 'references', json.dumps({'results':references}, ensure_ascii=False), now))

    def recover(self):
        # A process restart never repeats scientific computations silently.
        with self.db() as db:
            db.execute("UPDATE turns SET status='interrupted',error='The execution lease expired. Saved results are available; start a new turn to continue.' WHERE status IN ('queued','running') AND (lease_expires<=? OR created<=?)", (time.time(), time.time()-7200))
            agent_quota.reconcile(db)

    def save_result(self, owner, tool, inputs, payload, session_id=None, turn_id=None, duration=0):
        result_id = uid()
        title = TOOLS.get(tool, (None, None, tool, None))[2]
        from .blast_jobs import result_status
        status = "running" if tool == "structure" and payload.get("status") == "running" else result_status(payload)
        with self.db() as db:
            db.execute("INSERT INTO results(id,owner,session_id,turn_id,tool,title,status,inputs,payload,created,duration) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (result_id, owner, session_id, turn_id, tool, title, status,
                        json.dumps(inputs, ensure_ascii=False), json.dumps(payload, ensure_ascii=False), time.time(), duration))
        return self.result(owner, result_id)

    def result(self, owner, result_id, full=True):
        columns = '*' if full else 'id,session_id,turn_id,tool,title,status,inputs,created,duration'
        with self.db() as db:
            row = db.execute(f"SELECT {columns} FROM results WHERE owner=? AND id=?", (owner, result_id)).fetchone()
        if not row:
            raise HTTPException(404, "Result not found in this workspace. It may have been automatically deleted after the 90-day retention period.")
        result = dict(row)
        result.pop("owner", None)
        for key in (("inputs", "payload") if full else ("inputs",)):
            result[key] = json.loads(result[key])
        if full and result["tool"] == "active-sites":
            # Normalize on read so historical evidence and sandbox inputs receive
            # the same residue sequence without rewriting the archived response.
            result["payload"] = normalize_active_site_payload(result["payload"])
        result["evidence_type"] = TOOLS.get(result["tool"], (None, None, None, "Analysis"))[3]
        result["url"] = f"/enzymind/results/{result_id}"
        result.update(expiry_fields(result['created']))
        if not full:
            result["inputs"] = compact(result["inputs"])
        return result

    def results(self, owner, session_id=None):
        sql, params = "SELECT id FROM results WHERE owner=?", [owner]
        if session_id:
            self.session(owner, session_id)
            sql += " AND session_id=?"
            params.append(session_id)
        with self.db() as db:
            rows = db.execute(sql + " ORDER BY created DESC LIMIT 200", params).fetchall()
        return [self.result(owner, r["id"], full=False) for r in rows]
