import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from gateway import workspace
from gateway.workspace_store import WorkspaceStore, digest
from gateway.workspace_stream import read_workflow_response


def frame(node, content=None, kind='item'):
    return (json.dumps({'type':kind,'metadata':{'nodeName':node},'content':content}, ensure_ascii=False)+'\n').encode()


class BytesStream(httpx.AsyncByteStream):
    def __init__(self, iterator): self.iterator = iterator
    async def __aiter__(self):
        async for value in self.iterator: yield value


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        workspace._store = WorkspaceStore(Path(self.tmp.name)/'workspace.sqlite')
        self.key = digest('a'*64)
        self.session = workspace.store().create_session(self.key)
        self.turn, self.token = workspace.store().begin(self.key,self.session['id'],str(uuid4()),'Stream an answer',[])
    def tearDown(self):
        workspace._store = None
        self.tmp.cleanup()
    def mock_client(self, chunks):
        real = httpx.AsyncClient
        return patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=BytesStream(chunks))),**kw))
    def saved(self): return workspace.store().turn(self.key,self.turn['id'])
    def memory(self): return workspace.store().session(self.key,self.session['id'])

    async def test_text_arrives_before_final_and_only_completion_commits_memory(self):
        arrived,release=asyncio.Event(),asyncio.Event()
        async def chunks():
            yield frame('Summarize older turns','PRIVATE MEMORY MUST NOT STREAM')
            raw=frame('Research Agent','酶学研究🧬')
            for byte in raw: yield bytes([byte])  # Split UTF-8 and JSON arbitrarily.
            arrived.set();await release.wait()
            yield frame('Research Agent',kind='end')
            yield frame('Workspace response',json.dumps({'output':'酶学研究🧬 complete','summary':'','summarized_count':0,'memory_revision':0}))
        with self.mock_client(chunks()):
            task=asyncio.create_task(workspace.run_turn(self.key,self.turn,self.token))
            await asyncio.wait_for(arrived.wait(),2)
            self.assertEqual(self.saved()['partial_output'],'酶学研究🧬')
            self.assertEqual(self.saved()['status'],'running')
            self.assertEqual(self.memory()['memory_revision'],0)
            release.set();await task
        self.assertEqual(self.saved()['status'],'completed')
        self.assertEqual(self.saved()['partial_output'],'')
        self.assertEqual(self.saved()['output'],'酶学研究🧬 complete')
        self.assertEqual(self.memory()['memory_revision'],1)

    async def test_missing_final_envelope_preserves_partial_and_memory(self):
        async def chunks():
            yield frame('Research Agent','Incomplete answer')
            yield frame('Research Agent',kind='end')
        with self.mock_client(chunks()): await workspace.run_turn(self.key,self.turn,self.token)
        self.assertEqual(self.saved()['status'],'failed')
        self.assertEqual(self.saved()['partial_output'],'Incomplete answer')
        self.assertEqual(self.saved()['output'],'')
        self.assertEqual(self.memory()['memory_revision'],0)
        self.assertIn('ended before completion',self.saved()['error'])

    async def test_failed_completion_cannot_commit_streamed_answer(self):
        async def chunks():
            yield frame('Research Agent','Draft')
            yield frame('Workspace response',json.dumps({'error':'Memory validation failed'}))
        with self.mock_client(chunks()): await workspace.run_turn(self.key,self.turn,self.token)
        self.assertEqual(self.saved()['status'],'failed')
        self.assertEqual(self.saved()['partial_output'],'Draft')
        self.assertEqual(self.memory()['memory_revision'],0)

    async def test_stop_preserves_text_and_rejects_late_chunks(self):
        arrived=asyncio.Event()
        async def chunks():
            yield frame('Research Agent','Already received')
            arrived.set();await asyncio.Event().wait()
        with self.mock_client(chunks()):
            task=asyncio.create_task(workspace.run_turn(self.key,self.turn,self.token))
            await asyncio.wait_for(arrived.wait(),2)
            workspace.store().status(self.key,self.turn['id'],'cancelled',error='Stopped')
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.saved()['status'],'cancelled')
        self.assertEqual(self.saved()['partial_output'],'Already received')
        self.assertFalse(workspace.store().append_partial(self.key,self.turn['id'],'late'))
        self.assertEqual(self.memory()['memory_revision'],0)

    async def test_sse_snapshot_delta_reconnect_final_and_owner_isolation(self):
        class Request:
            headers={'x-enzymind-client':'a'*64}
            async def is_disconnected(self): return False
        workspace.store().status(self.key,self.turn['id'],'running')
        workspace.store().append_partial(self.key,self.turn['id'],'First')
        response=await workspace.stream_turn(self.turn['id'],Request())
        self.assertEqual(response.headers['x-accel-buffering'],'no')
        iterator=response.body_iterator
        self.assertIn('First',await anext(iterator))
        workspace.store().append_partial(self.key,self.turn['id'],'第二')
        delta=await anext(iterator)
        self.assertIn('event: delta',delta);self.assertIn('第二',delta);self.assertNotIn('First',delta)
        await iterator.aclose()  # A browser disconnect does not cancel the turn.
        self.assertEqual(self.saved()['status'],'running')
        reopened=WorkspaceStore(workspace.store().path)
        self.assertEqual(reopened.turn(self.key,self.turn['id'])['partial_output'],'First第二')
        again=await workspace.stream_turn(self.turn['id'],Request());iterator=again.body_iterator
        self.assertIn('First第二',await anext(iterator))
        workspace.store().complete(self.key,self.turn['id'],0,'Final answer','',0,[])
        rest=[chunk async for chunk in iterator]
        self.assertIn('event: done',''.join(rest));self.assertIn('Final answer',''.join(rest))
        other=Request();other.headers={'x-enzymind-client':'b'*64}
        with self.assertRaises(HTTPException) as e: await workspace.stream_turn(self.turn['id'],other)
        self.assertEqual(e.exception.status_code,404)

    async def test_malformed_stream_and_error_frame_are_not_success(self):
        for content in [b'{"type":',frame('Research Agent',kind='error')]:
            response=httpx.Response(200,content=content)
            with self.assertRaises(ValueError): await read_workflow_response(response,lambda text:None)
