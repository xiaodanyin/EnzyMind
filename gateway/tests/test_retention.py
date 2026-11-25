"""Retention tests use only temporary databases and dedicated temporary files."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from gateway import workspace
from gateway.main import app
from gateway.retention import initialize_vacuum, prune_files, purge_records, run_cleanup
from gateway.retention_policy import RETENTION_SECONDS
from gateway.workspace_store import WorkspaceStore, digest


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = WorkspaceStore(self.root / 'workspace.sqlite3')
        self.owner = digest('a' * 64)
        self.now = time.time()
        self.cutoff = self.now - RETENTION_SECONDS

    def session(self, created=None):
        session = self.store.create_session(self.owner)
        if created is not None:
            with self.store.db() as db:
                db.execute('UPDATE sessions SET created=? WHERE id=?', (created, session['id']))
        return session['id']

    def turn(self, sid, created, *, active=False, refs=()):
        turn, _ = self.store.begin(self.owner, sid, str(uuid4()), 'Research question', list(refs))
        self.store.status(self.owner, turn['id'], 'running' if active else 'completed', output='' if active else 'Answer')
        self.store.event(turn['id'], 'tool_start', {'tool': 'kcat'})
        with self.store.db() as db:
            db.execute('UPDATE turns SET created=?,updated=? WHERE id=?', (created, created, turn['id']))
            db.execute('UPDATE events SET created=? WHERE turn_id=?', (created, turn['id']))
        return turn['id']

    def result(self, created, *, sid=None, tid=None, tool='kcat', payload=None):
        result = self.store.save_result(self.owner, tool, {'query': 'P00761'}, payload or {'kcat': 1}, sid, tid)
        with self.store.db() as db:
            db.execute('UPDATE results SET created=? WHERE id=?', (created, result['id']))
        return result['id']

    def exists(self, table, rid):
        with self.store.db() as db:
            return bool(db.execute(f'SELECT 1 FROM {table} WHERE id=?', (rid,)).fetchone())

    def cleanup(self, **kwargs):
        return run_cleanup(self.store, now=self.now, artifact_roots=[], **kwargs)

    def test_boundary_recent_children_and_memory_reset(self):
        sid = self.session(self.cutoff - 100)
        old_turn = self.turn(sid, self.cutoff)
        recent_turn = self.turn(sid, self.cutoff + 1)
        old_result = self.result(self.cutoff, sid=sid, tid=old_turn)
        recent_result = self.result(self.cutoff + .001, sid=sid, tid=old_turn)
        empty_sid = self.session(self.cutoff)
        orphan_result = self.result(self.now, sid=empty_sid)
        untouched_sid = self.session()
        with self.store.db() as db:
            db.execute("UPDATE sessions SET summary='Old context', summarized_count=2, memory_revision=4, context_tokens=5000 WHERE id=?", (sid,))
            db.execute("UPDATE sessions SET summary='Valid context' WHERE id=?", (untouched_sid,))
        # Viewing an old result must not extend its expiry.
        self.assertEqual(self.store.result(self.owner, old_result)['expires_at'], self.now)
        report = self.cleanup()
        self.assertEqual(report['records'], {'results': 1, 'turns': 1, 'events': 1, 'sessions': 1, 'memory_resets': 1})
        self.assertFalse(self.exists('results', old_result))
        self.assertFalse(self.exists('turns', old_turn))
        self.assertTrue(self.exists('turns', recent_turn))
        self.assertFalse(self.exists('sessions', empty_sid))
        kept = self.store.result(self.owner, recent_result)
        self.assertIsNone(kept['turn_id'])
        self.assertEqual(kept['session_id'], sid)
        self.assertIsNone(self.store.result(self.owner, orphan_result)['session_id'])
        session = self.store.session(self.owner, sid)
        self.assertEqual((session['summary'], session['summarized_count'], session['memory_revision']), ('', 0, 5))
        self.assertEqual(session['retention_reset_at'], self.now)
        self.assertEqual(self.store.session(self.owner, untouched_sid)['summary'], 'Valid context')
        self.assertEqual(len(self.store.turn(self.owner, recent_turn)['events']), 1)
        # Maintenance history is a singleton, not another growing event log.
        self.cleanup()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM maintenance').fetchone()[0], 1)

    def test_live_turn_protects_context_attachments_and_read_results(self):
        sid = self.session(self.cutoff - 100)
        old_turn = self.turn(sid, self.cutoff - 1)
        same_session = self.result(self.cutoff, sid=sid)
        attachment = self.result(self.cutoff)
        read_result = self.result(self.cutoff)
        unrelated = self.result(self.cutoff)
        active_turn = self.turn(sid, self.now, active=True, refs=[attachment])
        self.store.event(active_turn, 'tool_end', {'tool': 'read-result', 'result_id': read_result})
        self.cleanup()
        self.assertTrue(self.exists('turns', old_turn))
        for rid in [same_session, attachment, read_result]:
            self.assertTrue(self.exists('results', rid))
        self.assertFalse(self.exists('results', unrelated))
        self.store.status(self.owner, active_turn, 'completed', output='Finished safely')
        self.cleanup()
        self.assertFalse(self.exists('turns', old_turn))
        for rid in [same_session, attachment, read_result]:
            self.assertFalse(self.exists('results', rid))
        self.assertTrue(self.exists('turns', active_turn))

    def test_stale_lease_cannot_protect_expired_records_forever(self):
        sid = self.session(self.cutoff - 100)
        old_turn = self.turn(sid, self.cutoff)
        rid = self.result(self.cutoff, sid=sid)
        active = self.turn(sid, self.now, active=True)
        with self.store.db() as db:
            db.execute('UPDATE turns SET lease_expires=? WHERE id=?', (self.now - 1, active))
        self.cleanup()
        self.assertFalse(self.exists('results', rid))
        self.assertFalse(self.exists('turns', old_turn))
        self.assertEqual(self.store.turn(self.owner, active)['status'], 'interrupted')

    def file(self, relative, *, age=91):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Synthetic test file')
        stamp = self.now - age * 86400
        os.utime(path, (stamp, stamp))
        return path

    def test_dry_run_file_allowlist_symlinks_and_surviving_references(self):
        retired = self.file('artifacts/old_0123456789ab/old_0123456789ab.pdb')
        retired_log = self.file('artifacts/logs/old_0123456789ab.err')
        kept = self.file('artifacts/keep_0123456789ab/keep_0123456789ab.pdb')
        recent = self.file('artifacts/new_0123456789ab.fasta', age=1)
        unrelated = self.file('artifacts/reference.pdb')
        outside = self.file('outside_0123456789ab.pdb')
        (self.root / 'artifacts/link_0123456789ab.pdb').symlink_to(outside)
        outside_dir = self.root / 'external'
        linked = self.file('external/link_0123456789ab.pdb')
        (self.root / 'artifacts/link_dir').symlink_to(outside_dir, target_is_directory=True)
        backup = self.file('backups/old.sqlite3')
        recent_backup = self.file('backups/new.sqlite3', age=1)
        other_backup = self.file('backups/notes.txt')
        rid = self.result(self.cutoff, tool='structure', payload={'pdb_path': str(retired)})
        self.result(self.now, tool='structure', payload={'static_path': '/static/pdb/keep_0123456789ab.pdb'})
        kwargs = dict(now=self.now, artifact_roots=[str(self.root / 'artifacts')])
        report = run_cleanup(self.store, dry_run=True, **kwargs)
        self.assertEqual(report['records']['results'], 1)
        self.assertEqual(report['artifacts']['files'], 2)
        self.assertEqual(report['backups']['files'], 1)
        self.assertTrue(retired.exists())
        self.assertTrue(backup.exists())
        self.assertTrue(self.exists('results', rid))
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM maintenance').fetchone()[0], 0)
        real = run_cleanup(self.store, **kwargs)
        self.assertEqual(real['artifacts'], report['artifacts'])
        self.assertFalse(retired.exists())
        self.assertFalse(retired_log.exists())
        self.assertFalse(backup.exists())
        for path in [kept, recent, unrelated, outside, linked, recent_backup, other_backup]:
            self.assertTrue(path.exists(), str(path))
        # Never permit the backup cleaner to encompass the live database.
        with self.assertRaises(ValueError):
            self.cleanup(backup_root=self.root)
        self.assertEqual(prune_files(self.root / 'artifacts/link_dir', self.cutoff)['files'], 0)

    def test_batch_limit_and_next_pass(self):
        ids = [self.result(self.cutoff) for _ in range(3)]
        first = purge_records(self.store, now=self.now, batch_size=2)
        self.assertEqual(first['results'], 2)
        self.assertEqual(sum(self.exists('results', rid) for rid in ids), 1)
        self.assertEqual(self.cleanup()['records']['results'], 1)

    def test_incremental_vacuum_reclaims_database_pages(self):
        rid = self.result(self.cutoff, payload={'blob': 'x' * 2_000_000})
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA auto_vacuum').fetchone()[0], 2)
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        before = self.store.path.stat().st_size
        report = self.cleanup()
        self.assertFalse(self.exists('results', rid))
        self.assertTrue(report['storage']['incremental_vacuum'])
        self.assertGreater(report['storage']['pages_reclaimed'], 400)
        self.assertLess(self.store.path.stat().st_size, before // 2)

    def test_existing_database_vacuum_migration_preserves_data(self):
        path = self.root / 'legacy.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE legacy (value TEXT)')
            db.execute("INSERT INTO legacy VALUES ('existing research')")
        store = WorkspaceStore(path)
        with store.db() as db:
            self.assertEqual(db.execute('PRAGMA auto_vacuum').fetchone()[0], 0)
        self.assertEqual(initialize_vacuum(store)['auto_vacuum'], 2)
        with store.db() as db:
            self.assertEqual(db.execute('SELECT value FROM legacy').fetchone()[0], 'existing research')

    def test_api_policy_expiry_404_and_hourly_scheduler(self):
        calls = []
        def cleanup(store):
            calls.append(run_cleanup(store, artifact_roots=[]))
        rid = self.result(self.now)
        expired = self.result(self.cutoff - 1)
        with patch.object(workspace, '_store', self.store), patch.object(workspace, 'run_cleanup', cleanup), patch.object(workspace, 'CLEANUP_INTERVAL_SECONDS', .02):
            with TestClient(app) as client:
                headers = {'X-Enzymind-Client': 'a' * 64}
                policy = client.get('/api/workspace/retention').json()
                self.assertEqual(policy['retention_days'], 90)
                result = client.get(f'/api/workspace/results/{rid}', headers=headers).json()
                self.assertEqual(result['expires_at'], self.now + RETENTION_SECONDS)
                self.assertEqual(result['retention_days'], 90)
                gone = client.get(f'/api/workspace/results/{expired}', headers=headers)
                self.assertEqual(gone.status_code, 404)
                self.assertIn('90-day', gone.json()['detail'])
                foreign = client.get(f'/api/workspace/results/{rid}', headers={'X-Enzymind-Client': 'b' * 64})
                self.assertEqual(foreign.status_code, 404)
                client.portal.call(asyncio.sleep, .09)
                self.assertGreaterEqual(len(calls), 2)
            self.assertIsNone(workspace._retention_task)


if __name__ == '__main__':
    unittest.main()
