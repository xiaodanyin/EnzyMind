"""Bounded 90-day cleanup of EnzyMind records and managed artifacts.

Run `python -m gateway.retention --dry-run` to review candidates. The gateway
runs this maintenance at startup and hourly. n8n's shared database is excluded.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time

from .retention_policy import RETENTION_DAYS, RETENTION_SECONDS
from .agent_quota import reconcile as reconcile_usage

logger = logging.getLogger('enzymind.retention')
DEFAULT_ARTIFACT_ROOTS = ('/tmp/esmfold_output', '/tmp/esmfold_fasta', '/tmp/static/pdb')
JOB_NAME = re.compile(r'[A-Za-z0-9_-]{1,64}_[0-9a-f]{12}')


def purge_records(store, *, now=None, dry_run=False, batch_size=1000):
    """One transaction protects live sessions, their results and attachments."""
    now = time.time() if now is None else now
    cutoff = now - RETENTION_SECONDS
    if not 1 <= batch_size <= 10000: raise ValueError('Use a cleanup batch size between 1 and 10000.')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TEMP TABLE live_sessions(id TEXT PRIMARY KEY)')
        db.execute("INSERT INTO live_sessions SELECT DISTINCT session_id FROM turns WHERE status IN ('running','queued') AND lease_expires>? AND created>?", (now, now-7200))
        db.execute('CREATE TEMP TABLE protected_results(id TEXT PRIMARY KEY)')
        db.execute("INSERT OR IGNORE INTO protected_results SELECT j.value FROM turns t, json_each(t.refs) j WHERE t.status IN ('running','queued') AND t.lease_expires>? AND t.created>?", (now, now-7200))
        db.execute("INSERT OR IGNORE INTO protected_results SELECT json_extract(e.data,'$.result_id') FROM events e JOIN turns t ON t.id=e.turn_id WHERE e.kind='tool_end' AND json_extract(e.data,'$.result_id') IS NOT NULL AND t.status IN ('running','queued') AND t.lease_expires>? AND t.created>?", (now, now-7200))
        db.execute('CREATE TEMP TABLE expired_results(id TEXT PRIMARY KEY)')
        db.execute('INSERT INTO expired_results SELECT r.id FROM results r WHERE r.created<=? AND NOT EXISTS(SELECT 1 FROM live_sessions a WHERE a.id=r.session_id) AND NOT EXISTS(SELECT 1 FROM protected_results p WHERE p.id=r.id) ORDER BY r.created LIMIT ?', (cutoff,batch_size))
        db.execute('CREATE TEMP TABLE expired_turns(id TEXT PRIMARY KEY, session_id TEXT NOT NULL)')
        db.execute('INSERT INTO expired_turns SELECT id,session_id FROM turns WHERE created<=? AND session_id NOT IN (SELECT id FROM live_sessions) ORDER BY created LIMIT ?', (cutoff,batch_size))
        db.execute('CREATE TEMP TABLE expired_events(seq INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO expired_events SELECT seq FROM events WHERE turn_id IN (SELECT id FROM expired_turns)')
        db.execute('INSERT OR IGNORE INTO expired_events SELECT e.seq FROM events e WHERE (e.created<=? OR NOT EXISTS(SELECT 1 FROM turns t WHERE t.id=e.turn_id)) AND NOT EXISTS(SELECT 1 FROM turns t JOIN live_sessions a ON a.id=t.session_id WHERE t.id=e.turn_id) ORDER BY e.created LIMIT ?', (cutoff,batch_size))
        db.execute('CREATE TEMP TABLE empty_sessions(id TEXT PRIMARY KEY)')
        db.execute('INSERT INTO empty_sessions SELECT s.id FROM sessions s WHERE s.created<=? AND NOT EXISTS(SELECT 1 FROM turns t WHERE t.session_id=s.id AND t.id NOT IN (SELECT id FROM expired_turns)) AND s.id NOT IN (SELECT id FROM live_sessions) LIMIT ?', (cutoff,batch_size))
        affected = [r[0] for r in db.execute('SELECT DISTINCT session_id FROM expired_turns WHERE session_id NOT IN (SELECT id FROM empty_sessions)')]
        report = {name:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for name,table in [('results','expired_results'),('turns','expired_turns'),('events','expired_events'),('sessions','empty_sessions')]}
        report.update(memory_resets=len(affected), dry_run=dry_run)
        report['_expired_result_ids'] = [r[0] for r in db.execute('SELECT id FROM expired_results')]
        if not dry_run:
            from .python_sandbox import purge
            purge(db, now - 3600)
            # Newer results survive even when their parent turn/session expires.
            db.execute('UPDATE results SET turn_id=NULL WHERE turn_id IN (SELECT id FROM expired_turns)')
            db.execute('UPDATE results SET session_id=NULL WHERE session_id IN (SELECT id FROM empty_sessions)')
            db.execute('DELETE FROM results WHERE id IN (SELECT id FROM expired_results)')
            db.execute('DELETE FROM events WHERE seq IN (SELECT seq FROM expired_events)')
            db.execute('DELETE FROM turns WHERE id IN (SELECT id FROM expired_turns)')
            for sid in affected:
                db.execute("UPDATE sessions SET summary='',summarized_count=0,context_tokens=0,memory_revision=memory_revision+1,retention_reset_at=? WHERE id=?", (now,sid))
            db.execute('DELETE FROM sessions WHERE id IN (SELECT id FROM empty_sessions)')
            db.execute("UPDATE turns SET status='interrupted',error='The execution lease expired. Saved results remain available within their retention period.' WHERE status IN ('running','queued') AND (lease_expires<=? OR created<=?)", (now,now-7200))
            reconcile_usage(db, now)
        return report


def protected_job_names(store, exclude_ids=()):
    """Coordinates linked from any surviving result protect the whole job."""
    names = set()
    with store.db() as db:
        for row in db.execute("SELECT id,json_extract(payload,'$.pdb_path'),json_extract(payload,'$.static_path') FROM results WHERE tool='structure'"):
            if row[0] in exclude_ids: continue
            for path in row[1:]:
                if isinstance(path,str) and JOB_NAME.fullmatch(Path(path).stem):
                    names.add(Path(path).stem)
    return names


def prune_files(root, cutoff, *, backup=False, protected=(), dry_run=False, max_files=5000):
    """Only dedicated roots, recognized job files, no symlink traversal."""
    root = Path(root)
    report = {'files':0,'bytes':0,'errors':0}
    if not root.is_absolute() or len(root.parts)<3 or root.is_symlink() or root.resolve()!=root or not root.is_dir():
        return report
    directories = []
    for parent, dirs, files in os.walk(root, followlinks=False):
        parent = Path(parent)
        dirs[:] = [d for d in dirs if not (parent/d).is_symlink()]
        directories.append(parent)
        for name in files:
            path=parent/name
            if path.is_symlink(): continue
            suffix=path.suffix.lower()
            job = next((part for part in path.relative_to(root).parts[:-1] if JOB_NAME.fullmatch(part)), None)
            stem=path.stem
            if backup:
                allowed=suffix in {'.sqlite3','.sqlite','.db','.json'}
            else:
                allowed=suffix in {'.pdb','.fasta','.fa','.log','.err'} and (job or JOB_NAME.fullmatch(stem))
            if not allowed or job in protected or stem in protected: continue
            try:
                info=path.stat(follow_symlinks=False)
                if not path.is_file() or info.st_mtime>cutoff: continue
                if report['files']>=max_files: return report
                if not dry_run: path.unlink()
                report['files']+=1;report['bytes']+=info.st_size
            except OSError:
                report['errors']+=1
    if not dry_run:
        for directory in reversed(directories):
            if directory==root:continue
            try:
                if directory.stat().st_mtime<=cutoff:directory.rmdir()
            except OSError:pass  # Nonempty/recent directories remain.
    return report


def reclaim_space(store, max_pages=8192):
    """Return free pages gradually; avoid long full VACUUMs during traffic."""
    with sqlite3.connect(store.path,timeout=1) as db:
        mode=db.execute('PRAGMA auto_vacuum').fetchone()[0]
        before=db.execute('PRAGMA freelist_count').fetchone()[0]
        if mode==2 and before:db.execute(f'PRAGMA incremental_vacuum({int(max_pages)})').fetchall()
        after=db.execute('PRAGMA freelist_count').fetchone()[0]
        checkpoint=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        return {'incremental_vacuum':mode==2,'pages_reclaimed':before-after,'free_pages':after,'checkpoint_busy':checkpoint[0]}


def initialize_vacuum(store):
    """One-time existing-database migration; run with the gateway stopped."""
    with sqlite3.connect(store.path,timeout=2) as db:
        if db.execute("SELECT count(*) FROM turns WHERE status IN ('running','queued')").fetchone()[0]:
            raise RuntimeError('Wait for active Agent turns before initializing vacuum.')
        if db.execute('PRAGMA auto_vacuum').fetchone()[0]!=2:
            db.execute('PRAGMA auto_vacuum=INCREMENTAL')
            db.execute('VACUUM')
        return {'auto_vacuum':db.execute('PRAGMA auto_vacuum').fetchone()[0]}


def run_cleanup(store, *, now=None, dry_run=False, artifact_roots=None, backup_root=None):
    now=time.time() if now is None else now
    roots=artifact_roots if artifact_roots is not None else json.loads(os.getenv('ENZYMIND_RETENTION_ARTIFACT_ROOTS',json.dumps(DEFAULT_ARTIFACT_ROOTS)))
    if not isinstance(roots,list) and not isinstance(roots,tuple):raise ValueError('Artifact roots must be a JSON array of dedicated directories.')
    if any(not isinstance(root,str) or not Path(root).is_absolute() or len(Path(root).parts)<3 for root in roots):raise ValueError('Use absolute, dedicated artifact directories.')
    backups=Path(backup_root) if backup_root is not None else store.path.resolve().parent/'backups'
    if store.path.resolve().is_relative_to(backups.resolve()):
        raise ValueError('Backup cleanup cannot include the live database.')
    report={'retention_days':RETENTION_DAYS,'checked_at':now,'dry_run':dry_run,'records':{key:0 for key in ('results','turns','events','sessions','memory_resets')}}
    excluded=set()
    started=time.monotonic()
    for batch in range(1,101):
        counts=purge_records(store,now=now,dry_run=dry_run)
        excluded.update(counts.pop('_expired_result_ids'))
        for key in report['records']:report['records'][key]+=counts[key]
        report['batches']=batch
        report['backlog_possible']=any(counts[key]>=1000 for key in ('results','turns','events','sessions'))
        if dry_run or not report['backlog_possible'] or time.monotonic()-started>=30:break
    protected=protected_job_names(store,excluded)
    report['artifacts']={'files':0,'bytes':0,'errors':0}
    for root in roots:
        counts=prune_files(root,now-RETENTION_SECONDS,protected=protected,dry_run=dry_run)
        for key,value in counts.items():report['artifacts'][key]+=value
    report['backups']=prune_files(backups,now-RETENTION_SECONDS,backup=True,dry_run=dry_run)
    if not dry_run:
        try:report['storage']=reclaim_space(store)
        except sqlite3.OperationalError as exc:
            report['storage']={'deferred':True,'reason':str(exc)}
        with store.db() as db:
            db.execute('INSERT INTO maintenance(name,updated,report) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET updated=excluded.updated,report=excluded.report',('retention',now,json.dumps(report)))
    logger.info('Retention maintenance: %s',json.dumps(report))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--dry-run',action='store_true')
    action.add_argument('--run',action='store_true')
    action.add_argument('--initialize-vacuum',action='store_true')
    args=parser.parse_args()
    from .workspace_store import WorkspaceStore
    store=WorkspaceStore()
    print(json.dumps(initialize_vacuum(store) if args.initialize_vacuum else run_cleanup(store,dry_run=args.dry_run),indent=2))


if __name__=='__main__':main()
