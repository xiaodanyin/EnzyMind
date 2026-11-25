"""Durable NCBI jobs in the existing owner-scoped result store.

Only submission sends CMD=Put. Recovery and retries only retrieve a saved RID.
No database migration, extra job database, or changed retention clock is needed.
"""
import asyncio
import json
import os
import logging
import re
import time
from uuid import uuid4

import httpx
from fastapi import HTTPException

from .retention_policy import RETENTION_SECONDS
from .service_policy import service_timeout

PENDING = {'submitting', 'queued', 'paused'}
RID = r'[A-Z0-9-]{5,40}'
MESSAGE = 'NCBI is processing this search. Results will be retrieved in the background. You can close this page and return to Results. No alignments are available yet; do not infer any hits or resubmit this job.'


def result_status(payload):
    from .result_catalog import payload_error
    if payload_error(payload):
        return 'failed'
    return payload.get('status') if isinstance(payload, dict) and payload.get('status') in PENDING else 'completed'


class BlastJobs:
    def __init__(self, store, service_url):
        self.store, self.url = store, service_url
        self.task = None
        self.submissions = set()

    async def request(self, method, path, **kwargs):
        local = kwargs.get('json', {}).get('database') == 'local_uniprot'
        timeout = service_timeout('sequence_alignment') if local else 210
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15)) as client:
            response = await client.request(method, self.url + path, **kwargs)
            if response.is_error and local:
                failure = response.json()
                if isinstance(failure, dict) and failure.get("success") is False:
                    return {**failure, "status": "failed"}
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError('Invalid BLAST service response')
            return {k: v for k, v in payload.items() if v is not None}

    @staticmethod
    def inputs(raw):
        query = raw.get('query')
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(422, 'A protein sequence, FASTA, or UniProt accession is required.')
        database = raw.get('database') or ('local_uniprot' if os.getenv('ENZYMIND_BLAST_DB') else 'nr')
        maximum = raw.get('max_results', 3)
        allowed = {'nr', 'swissprot', 'local_uniprot'}
        if database not in allowed or isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 50:
            raise HTTPException(422, 'Choose a supported BLAST database, with 1–50 returned alignment segments.')
        return {'query': query.strip(), 'max_results': maximum, 'database': database}

    async def submit(self, owner, raw, session_id=None, turn_id=None):
        inputs = self.inputs(raw)
        if inputs['database'] == 'local_uniprot' and not os.getenv('ENZYMIND_BLAST_DB'):
            raise HTTPException(503, 'Local UniProt BLAST is disabled.')
        now, result_id = time.time(), str(uuid4())
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT id,inputs FROM results WHERE owner=? AND tool='blast' AND status IN ('submitting','queued','paused') AND created>?", (owner, now - RETENTION_SECONDS)).fetchall()
            existing = next((r for r in rows if self.inputs({'database': 'nr', **json.loads(r['inputs'])}) == inputs), None)
            if existing:
                result_id = existing['id']
            else:
                payload = {'success': True, 'status': 'submitting', 'database': inputs['database'], 'message': 'Submitting the search. This result will update when processing finishes.'}
                db.execute('INSERT INTO results(id,owner,session_id,turn_id,tool,title,status,inputs,payload,created,duration) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (result_id, owner, session_id, turn_id, 'blast', 'Sequence similarity · BLAST', 'submitting', json.dumps(inputs), json.dumps(payload), now, 0))
        if not existing:
            # Decouple acceptance from the browser/Agent connection lifetime.
            task = asyncio.create_task(self._submit(owner, result_id, inputs))
            self.submissions.add(task)
            task.add_done_callback(self.submissions.discard)
            if inputs['database'] == 'local_uniprot':
                await asyncio.wait({task}, timeout=12)
        return self.store.result(owner, result_id)

    def update(self, owner, result_id, fields):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM results WHERE owner=? AND id=?', (owner, result_id)).fetchone()
            if not row:  # Retention may have removed it while a request was in flight.
                return
            payload = {**json.loads(row['payload']), **fields}
            for field in ('error', 'last_poll_error'):
                if payload.get(field) is None:
                    payload.pop(field, None)
            db.execute('UPDATE results SET payload=?,status=? WHERE id=? AND owner=?',
                       (json.dumps(payload), result_status(payload), result_id, owner))

    async def _submit(self, owner, result_id, inputs):
        try:
            payload = await self.request('POST', '/api/query/blast', json={**inputs, 'wait_for_result': False})
            if payload.get('status') == 'queued':
                if not re.fullmatch(RID, str(payload.get('request_id', ''))):
                    raise ValueError('Missing NCBI request ID')
                payload.update(message=MESSAGE, auto_poll_until=time.time() + 86400, next_poll_at=time.time() + 60)
        except Exception as exc:
            payload = {'success': False, 'status': 'failed', 'error_code': 'submission_uncertain',
                       'error': f'Could not confirm NCBI submission ({type(exc).__name__}). It was not retried automatically, to avoid a duplicate search.'}
        if inputs["database"] == "local_uniprot":
            payload.setdefault("message", "Local UniProt search finished.")
            if payload.get("error_code") == "submission_uncertain":
                payload["error"] = "The local alignment worker could not confirm completion."
        self.update(owner, result_id, payload)

    def recover(self):
        now = time.time()
        with self.store.db() as db:
            rows = db.execute("SELECT * FROM results WHERE tool='blast' AND status IN ('failed','submitting') AND created>?", (now - RETENTION_SECONDS,)).fetchall()
        for row in rows:
            payload = json.loads(row['payload'])
            error = payload.get('error', '')
            match = re.search(r'(?:Request ID: |Cannot retrieve NCBI BLAST request )(' + RID + r')\b', error)
            if match and ('still queued' in error or 'Cannot retrieve NCBI BLAST request' in error):
                self.update(row['owner'], row['id'], {'success': True, 'status': 'queued', 'error': None,
                    'previous_queue_error': error, 'request_id': match.group(1), 'database': json.loads(row['inputs']).get('database', 'nr'),
                    'message': MESSAGE, 'next_poll_at': now + 60, 'auto_poll_until': now + 86400})
            elif row['status'] == 'submitting':
                self.update(row['owner'], row['id'], {'success': False, 'status': 'failed', 'error_code': 'submission_uncertain',
                    'error': 'The server restarted before this search could be confirmed. No duplicate search was submitted automatically.'})

    def refresh(self, owner, result_id):
        record = self.store.result(owner, result_id)
        payload = record['payload']
        if record['tool'] != 'blast' or record['status'] not in {'queued', 'paused'}:
            raise HTTPException(409, 'Only queued or paused BLAST searches can be checked. No new search was submitted.')
        if not re.fullmatch(RID, str(payload.get('request_id', ''))):
            raise HTTPException(409, 'No valid NCBI request ID is saved.')
        # Do not override a polling lease or the per-RID cooldown.
        self.update(owner, result_id, {'status': 'queued', 'auto_poll_until': time.time() + 86400,
            'message': MESSAGE, 'next_poll_at': max(time.time(), payload.get('next_poll_at', 0), payload.get('last_checked_at', 0) + 60)})
        return self.store.result(owner, result_id)

    async def tick(self):
        now = time.time()
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT * FROM results WHERE tool='blast' AND status='queued' AND created>? ORDER BY json_extract(payload,'$.next_poll_at'),created", (now - RETENTION_SECONDS,)).fetchall()
            selected = None
            for row in rows:
                payload = json.loads(row['payload'])
                if payload.get('auto_poll_until', now + 1) <= now:
                    payload.update(status='paused', message='Automatic checks paused after 24 hours. Check status to resume retrieval of this same NCBI request.')
                    db.execute("UPDATE results SET status='paused',payload=? WHERE id=?", (json.dumps(payload), row['id']))
                    continue
                if payload.get('next_poll_at', 0) <= now and selected is None:
                    selected = dict(row)
                    payload['next_poll_at'] = now + 240  # Durable lease, including across restarts.
                    db.execute('UPDATE results SET payload=? WHERE id=?', (json.dumps(payload), row['id']))
        if not selected:
            return False
        old = json.loads(selected['payload'])
        rid = old.get('request_id', '')
        inputs = json.loads(selected['inputs'])
        try:
            if not re.fullmatch(RID, rid):
                raise ValueError('Invalid saved NCBI ID')
            payload = await self.request('GET', f'/api/query/blast/results/{rid}', params={'max_results': inputs.get('max_results', 3), 'database': inputs.get('database', 'nr')})
            if payload.get('status') not in {'queued', 'completed', 'failed'}:
                raise ValueError('Missing BLAST job status')
            payload.setdefault('last_poll_error', None)
            if payload['status'] == 'queued':
                payload['message'] = MESSAGE
        except Exception as exc:
            payload = {'status': 'queued', 'success': True, 'last_poll_error': f'Retrieval temporarily unavailable ({type(exc).__name__}). Your request ID is saved; checking will continue.'}
        failures = old.get('poll_failures', 0) + 1 if payload.get('last_poll_error') else 0
        payload.update(last_checked_at=time.time(), next_poll_at=time.time() + min(300, 60 * max(1, failures)), poll_failures=failures)
        if payload['status'] == 'completed':
            payload.update(message='NCBI search completed.', completed_at=time.time())
        self.update(selected['owner'], selected['id'], payload)
        return True

    async def loop(self):
        while True:
            try:
                active = await self.tick()
            except Exception:
                logging.getLogger('enzymind.blast').exception('BLAST retrieval will be retried')
                active = False
            await asyncio.sleep(1 if active else 5)

    def start(self):
        self.recover()
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        tasks = [*self.submissions, *([self.task] if self.task else [])]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
