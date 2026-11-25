import asyncio
import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from gateway.blast_jobs import BlastJobs
from gateway.workspace_store import WorkspaceStore
from gateway.retention_policy import RETENTION_SECONDS


@pytest.fixture
def jobs(tmp_path):
    jobs = BlastJobs(WorkspaceStore(tmp_path / 'workspace.sqlite3'), 'http://unused')
    jobs.request = AsyncMock(return_value={'success':True,'status':'queued','request_id':'F60URTGC014','database':'nr'})
    return jobs


def test_concurrent_submissions_are_deduplicated_and_durable(jobs):
    async def scenario():
        a, b = await asyncio.gather(jobs.submit('owner',{'query':'MAAAA'}), jobs.submit('owner',{'query':'MAAAA','database':'nr','max_results':3}))
        await asyncio.gather(*jobs.submissions)
        assert a['id'] == b['id']
        assert jobs.request.await_count == 1
        record = jobs.store.result('owner',a['id'])
        assert record['status'] == 'queued'
        reopened = WorkspaceStore(jobs.store.path).result('owner', a['id'])
        assert reopened['payload']['request_id'] == 'F60URTGC014'
        c = await jobs.submit('other-owner',{'query':'MAAAA'})
        assert c['id'] != a['id']
        await asyncio.gather(*jobs.submissions)
        with pytest.raises(HTTPException) as error:
            jobs.refresh('other-owner',a['id'])
        assert error.value.status_code == 404
    asyncio.run(scenario())


def queued(jobs, **fields):
    return jobs.store.save_result('owner','blast',{'query':'P00698','max_results':3},
        {'success':True,'status':'queued','request_id':'F60URTGC014','sequence':'MAAAA','sequence_source':{'provider':'UniProt'},'next_poll_at':0,'auto_poll_until':time.time()+86400,**fields})


def test_polling_completes_original_record_and_preserves_input_provenance_expiry(jobs):
    record = queued(jobs)
    jobs.request.return_value = {'success':True,'status':'completed','alignments':[],'num_results':0,'query_length':5}
    asyncio.run(jobs.tick())
    updated = jobs.store.result('owner',record['id'])
    assert updated['status'] == 'completed'
    assert updated['created'] == record['created'] and updated['expires_at'] == record['expires_at']
    assert updated['inputs'] == record['inputs']
    assert updated['payload']['sequence_source']['provider'] == 'UniProt'
    assert jobs.request.call_args.args == ('GET','/api/query/blast/results/F60URTGC014')


def test_network_failure_stays_queued_and_manual_checks_respect_cooldown(jobs):
    record = queued(jobs)
    jobs.request.side_effect = httpx.ReadTimeout('temporary')
    asyncio.run(jobs.tick())
    updated = jobs.store.result('owner', record['id'])
    assert updated['status'] == 'queued' and updated['payload']['request_id'] == 'F60URTGC014'
    assert 'last_poll_error' in updated['payload']
    refreshed = jobs.refresh('owner', record['id'])
    assert refreshed['payload']['next_poll_at'] >= updated['payload']['next_poll_at']
    assert not asyncio.run(jobs.tick())
    assert jobs.request.await_count == 1


def test_restart_recovers_old_timeout_without_submitting(jobs):
    record = jobs.store.save_result('owner','blast',{'query':'P00698'}, {'success':False,'error':'NCBI BLAST is still queued after 14 minutes. Request ID: F60URTGC014. Retrieve it at https://blast.ncbi.nlm.nih.gov/'})
    unrelated = jobs.store.save_result('owner','blast',{'query':'BAD'}, {'success':False,'error':'Invalid input'})
    jobs.recover()
    recovered = jobs.store.result('owner',record['id'])
    assert recovered['status'] == 'queued'
    assert recovered['payload']['request_id'] == 'F60URTGC014'
    assert 'error' not in recovered['payload']
    assert recovered['created'] == record['created']
    assert jobs.store.result('owner',unrelated['id'])['status'] == 'failed'
    jobs.request.assert_not_called()


def test_submission_interrupted_does_not_resubmit_on_restart(jobs):
    record = jobs.store.save_result('owner','blast',{'query':'MAAAA'}, {'success':True,'status':'submitting'})
    jobs.recover()
    recovered = jobs.store.result('owner',record['id'])
    assert recovered['status'] == 'failed'
    assert recovered['payload']['error_code'] == 'submission_uncertain'
    jobs.request.assert_not_called()


def test_ambiguous_submission_never_retries(jobs):
    async def scenario():
        jobs.request.side_effect = httpx.ReadTimeout('uncertain')
        record = await jobs.submit('owner', {'query':'MAAAA'})
        await asyncio.gather(*jobs.submissions)
        saved = jobs.store.result('owner', record['id'])
        assert saved['payload']['error_code'] == 'submission_uncertain'
        jobs.recover()
        assert not await jobs.tick()
        assert jobs.request.await_count == 1
    asyncio.run(scenario())


def test_auto_poll_window_is_bounded_and_manual_resume_keeps_retention(jobs):
    record = queued(jobs, auto_poll_until=time.time()-1)
    assert not asyncio.run(jobs.tick())
    assert jobs.store.result('owner',record['id'])['status'] == 'paused'
    refreshed = jobs.refresh('owner',record['id'])
    assert refreshed['status'] == 'queued' and refreshed['expires_at'] == record['expires_at']
    assert refreshed['payload']['request_id'] == 'F60URTGC014'


def test_expired_records_are_not_polled_or_recovered(jobs):
    record = queued(jobs)
    with jobs.store.db() as db:
        db.execute('UPDATE results SET created=? WHERE id=?',(time.time()-RETENTION_SECONDS-1,record['id']))
    assert not asyncio.run(jobs.tick())
    jobs.request.assert_not_called()


def test_a_poll_lease_survives_coordinator_restart(jobs):
    queued(jobs, next_poll_at=time.time()+240)
    restarted = BlastJobs(WorkspaceStore(jobs.store.path), 'http://unused')
    restarted.request = AsyncMock()
    restarted.recover()
    assert not asyncio.run(restarted.tick())
    restarted.request.assert_not_called()


def test_database_choice_is_part_of_job_identity(jobs):
    async def scenario():
        a = await jobs.submit('owner',{'query':'MAAAA','database':'nr'})
        b = await jobs.submit('owner',{'query':'MAAAA','database':'swissprot'})
        assert a['id'] != b['id']
        await asyncio.gather(*jobs.submissions)
        assert jobs.request.await_count == 2
    asyncio.run(scenario())


def test_browser_and_agent_routes_use_saved_jobs_and_enforce_ownership(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from gateway import workspace
    from gateway.main import app
    from gateway.workspace_store import digest
    monkeypatch.setattr(workspace, '_store', WorkspaceStore(tmp_path / 'api.sqlite3'))
    monkeypatch.setenv('ENZYMIND_RETENTION_ARTIFACT_ROOTS', '[]')
    monkeypatch.setattr(BlastJobs, 'request', AsyncMock(return_value={'success':True,'status':'queued','request_id':'F60URTGC014'}))
    headers = {'X-Enzymind-Client':'a'*64}
    owner = digest('a'*64)
    with TestClient(app) as client:
        result = client.post('/api/query/blast',headers=headers,json={'query':'P00698'}).json()
        result_id = result['workspace_result']['id']
        assert result['status'] == 'submitting'
        assert client.get('/api/workspace/results/'+result_id,headers=headers).json()['status'] in {'queued','submitting'}
        assert client.post('/api/workspace/results/'+result_id+'/refresh',headers={'X-Enzymind-Client':'b'*64}).status_code == 404
        assert client.post('/api/query/blast',headers=headers,json={'query':'P00698'}).json()['workspace_result']['id'] == result_id
        session = workspace.store().create_session(owner)
        turn, token = workspace.store().begin(owner,session['id'],'test-blast-agent','Find homologues',[])
        workspace.store().status(owner,turn['id'],'running')
        response = client.post('/api/workspace/tools/blast',headers={'X-Enzymind-Turn':token},json={'query':'MAAAA'}).json()
        assert response['status'] == 'submitting'
        assert 'Do not infer hits' in response['message']
        assert response['id'] != result_id
        assert workspace.store().result(owner,response['id'])['session_id'] == session['id']
        assert client.post('/api/query/blast',headers=headers,json={'query':'P00698','database':'bad'}).status_code == 422


def test_retention_deletes_queued_results_on_original_schedule(jobs):
    from gateway.retention import purge_records
    record = queued(jobs)
    with jobs.store.db() as db:
        db.execute('UPDATE results SET created=? WHERE id=?',(time.time()-RETENTION_SECONDS-1,record['id']))
    report = purge_records(jobs.store)
    assert report['results'] == 1
    with pytest.raises(HTTPException):
        jobs.store.result('owner',record['id'])


def test_local_default_returns_saved_alignments_and_preserves_remote_jobs(jobs, monkeypatch):
    async def scenario():
        old = await jobs.submit('owner', {'query': 'MAAAA'})
        await asyncio.gather(*jobs.submissions)
        with jobs.store.db() as db:
            db.execute('UPDATE results SET inputs=? WHERE id=?', ('{"query":"MAAAA"}', old['id']))
        monkeypatch.setenv('ENZYMIND_BLAST_DB', '/installed/uniprot')
        jobs.request.return_value = {'success': True, 'database': 'local_uniprot',
                                     'status': 'completed', 'alignments': [], 'num_results': 0}
        local = await jobs.submit('owner', {'query': 'MAAAA'})
        assert local['id'] != old['id'] and local['status'] == 'completed'
        assert local['payload']['database'] == 'local_uniprot'
        assert (await jobs.submit('owner', {'query': 'MAAAA', 'database': 'nr'}))['id'] == old['id']
    asyncio.run(scenario())
