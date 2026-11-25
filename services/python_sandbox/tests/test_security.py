import asyncio
import base64
import io
import json
import tarfile
import unittest
from unittest.mock import AsyncMock

import httpx

from services.python_sandbox.engine import Engine, Limits, container_config, volume_config, LABEL
from services.python_sandbox.protocol import (
    CODE_BYTES, FILE_BYTES, OUTPUT_BYTES, Rejected, input_archive, output_archive, validate_files,
)
from services.python_sandbox.selftest import resource_probe


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as tar:
        for name, kind, raw in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(raw) if kind == tarfile.REGTYPE else 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = 'work/code.py'
            tar.addfile(member, io.BytesIO(raw) if member.isfile() else None)
    return out.getvalue()


class ArchiveTests(unittest.TestCase):
    def test_roundtrip_json_csv_text(self):
        raw = archive([('work/result.json', tarfile.REGTYPE, b'{"length":6}'),
                       ('work/output/table.csv', tarfile.REGTYPE, b'id,length\none,6\n')])
        result, files = output_archive(raw)
        self.assertEqual(result, {'length': 6})
        self.assertEqual(validate_files(files)[0][2], b'id,length\none,6\n')
        packed = input_archive('result=1', {'data': {}, 'results': {}, 'files': {}}, files)
        with tarfile.open(fileobj=io.BytesIO(packed)) as tar:
            self.assertEqual(tar.getmember('code.py').uid, 10001)

    def test_reject_traversal_links_devices_duplicates_and_nested_files(self):
        for name, kind in [('../x', tarfile.REGTYPE), ('/work/output/x.txt', tarfile.REGTYPE),
            ('work/output/../../x.txt', tarfile.REGTYPE), ('work/output/link.txt', tarfile.SYMTYPE),
            ('work/inputs/hidden.txt', tarfile.LNKTYPE), ('work/output/dev.txt', tarfile.CHRTYPE),
            ('work/output/pipe.txt', tarfile.FIFOTYPE), ('work/output/dir/a.txt', tarfile.REGTYPE),
            ('work/output/x.html', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind), self.assertRaises(Rejected):
                output_archive(archive([(name, kind, b'x')]))
        with self.assertRaises(Rejected):
            output_archive(archive([('work/output/x.txt', tarfile.REGTYPE, b'x')] * 2))

    def test_bounds_are_bytes_not_characters(self):
        with self.assertRaises(Rejected):
            input_archive('中' * (CODE_BYTES // 2), {}, [])
        for entries in [
            [('work/output/x.txt', tarfile.REGTYPE, b'x' * (FILE_BYTES + 1))],
            [(f'work/output/{i}.txt', tarfile.REGTYPE, b'x') for i in range(11)],
            [(f'work/output/{i}.txt', tarfile.REGTYPE, b'x' * FILE_BYTES) for i in range(3)],
            [('work/result.json', tarfile.REGTYPE, b' ' * (OUTPUT_BYTES + 1))],
        ]:
            with self.assertRaises(Rejected):
                output_archive(archive(entries))

    def test_png_and_json_mime_cannot_disguise_html_or_nonfinite_numbers(self):
        for name, raw in [('x.png', b'<html>x</html>'), ('x.json', b'{"x":NaN}'), ('x.txt', b'\xff')]:
            with self.assertRaises(Rejected):
                validate_files([{'name': name, 'content': base64.b64encode(raw).decode()}])

    def test_policy_and_selftest_compile(self):
        config = container_config('sha256:' + 'a' * 64, 'job', Limits())
        self.assertEqual(config['HostConfig']['MemorySwap'], config['HostConfig']['Memory'])
        self.assertEqual(config['HostConfig']['NetworkMode'], 'none')
        self.assertEqual(config['HostConfig']['PidsLimit'], 64)
        self.assertNotIn('Binds', config['HostConfig'])
        self.assertEqual(config['HostConfig']['Mounts'][0]['Source'], 'enzymind-python-job')
        self.assertTrue(config['HostConfig']['Mounts'][0]['VolumeOptions']['NoCopy'])
        volume = volume_config('job', Limits())
        self.assertEqual(volume['DriverOpts']['type'], 'tmpfs')
        self.assertIn('size=134217728', volume['DriverOpts']['o'])
        self.assertEqual(volume['Labels'][LABEL+'.job'], 'job')
        self.assertNotIn('seccomp=unconfined', config['HostConfig']['SecurityOpt'])
        compile(resource_probe(Limits()), '<resource-probe>', 'exec')
        with self.assertRaises(ValueError):
            Engine('/tmp/not-used', 'python:latest')


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = Engine('/tmp/not-used', 'sha256:' + 'a' * 64)
        self.engine.remove_volume = AsyncMock()

    async def asyncTearDown(self):
        await self.engine.client.aclose()

    async def test_timeout_cancellation_and_lost_create_always_remove_by_known_name(self):
        for mode in ('timeout', 'cancel', 'lost_create'):
            self.engine.remove_volume.reset_mock()
            cancel = asyncio.Event()
            async def blocked(*args, **kwargs):
                if mode == 'cancel':
                    cancel.set()
                if mode == 'lost_create':
                    raise httpx.ReadError('response lost')
                await asyncio.sleep(10)
            self.engine.api = blocked
            self.engine.remove = AsyncMock()
            result = await self.engine.execute('abc', 'result=1', {}, [], cancel, limits=Limits(seconds=.02))
            self.assertEqual(result['execution_status'], {'timeout':'timeout', 'cancel':'cancelled', 'lost_create':'runner_transport_error'}[mode])
            self.engine.remove.assert_awaited_once_with('enzymind-python-abc')
            self.engine.remove_volume.assert_awaited_once_with('enzymind-python-abc')

    async def test_multiplex_output_and_frame_bound(self):
        def frame(stream, raw):
            return bytes([stream, 0, 0, 0]) + len(raw).to_bytes(4, 'big') + raw
        for content, rejected in [(frame(1, b'out') + frame(2, b'err'), False),
                                  (frame(1, b'x' * (OUTPUT_BYTES + 1)), True)]:
            def handle(request):
                if request.url.path.endswith('/start'):
                    return httpx.Response(200, content=content)
                return httpx.Response(200, json={'Id':'exec', 'Running':False, 'ExitCode':0})
            await self.engine.client.aclose()
            self.engine.client = httpx.AsyncClient(transport=httpx.MockTransport(handle), base_url='http://docker')
            out, err = bytearray(), bytearray()
            if rejected:
                with self.assertRaisesRegex(Rejected, 'output_limit'):
                    await self.engine.exec_stream('c', ['python'], out, err)
            else:
                self.assertEqual(await self.engine.exec_stream('c', ['python'], out, err), 0)
                self.assertEqual((out, err), (b'out', b'err'))
            self.assertLessEqual(len(out) + len(err), OUTPUT_BYTES)

    async def test_reaper_only_removes_expired_labelled_jobs(self):
        from services.python_sandbox.engine import LABEL
        self.engine.api = AsyncMock(side_effect=[
            [{'Id':'old', 'Labels': {LABEL+'.expires':'1'}},
             {'Id':'new', 'Labels': {LABEL+'.expires':'99999999999'}}],
            {'Volumes': [{'Name': 'old-volume', 'Labels': {LABEL+'.expires':'1'}},
                         {'Name': 'new-volume', 'Labels': {LABEL+'.expires':'99999999999'}}]}])
        self.engine.remove = AsyncMock()
        self.assertEqual(await self.engine.reap(), 2)
        self.engine.remove.assert_awaited_once_with('old')
        self.engine.remove_volume.assert_awaited_once_with('old-volume')
        self.assertIn(LABEL + '=v1', self.engine.api.call_args.kwargs['params']['filters'])

    async def test_effective_limit_failure_prevents_input_copy_and_user_execution(self):
        volume = volume_config('job', Limits())
        self.engine.api=AsyncMock(return_value={'Driver':'local', 'Options':volume['DriverOpts'], 'Labels':volume['Labels']})
        self.engine.exec_stream=AsyncMock(return_value=1)
        self.engine.remove=AsyncMock()
        result=await self.engine.execute('job','print("private scientific input")',{},[],asyncio.Event())
        self.assertEqual(result['execution_status'],'isolation_check_failed')
        self.assertFalse(any(call.args[0]=='PUT' for call in self.engine.api.call_args_list))
        self.engine.exec_stream.assert_awaited_once()
        compile(self.engine.exec_stream.call_args.args[1][-1], '<effective-limits-probe>', 'exec')
        self.engine.remove.assert_awaited_once()

    async def test_only_frozen_container_output_is_read_and_container_is_destroyed(self):
        calls=[]
        async def api(method,path,**kwargs):
            calls.append((method,path))
            if path=='/volumes/create':
                volume=kwargs['json']
                return {'Driver':volume['Driver'], 'Options':volume['DriverOpts'], 'Labels':volume['Labels']}
            if path.endswith('/json'): return {'State':{'Paused':True}}
            if path.endswith('/stats'): return {'memory_stats':{'usage':123}}
            return {}
        def response(request):
            self.assertTrue(any(path.endswith('/pause') for _,path in calls))
            self.assertTrue(any(path.endswith('/json') for _,path in calls))
            return httpx.Response(200,content=archive([('work/result.json',tarfile.REGTYPE,b'{"x":1}')]))
        await self.engine.client.aclose()
        self.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(response),base_url='http://docker')
        self.engine.api=api
        self.engine.exec_stream=AsyncMock(return_value=0)
        self.engine.remove=AsyncMock()
        result=await self.engine.execute('job','result={"x":1}',{},[],asyncio.Event())
        self.assertTrue(result['success'])
        self.assertEqual(result['result'],{'x':1})
        self.engine.remove.assert_awaited_once()
        self.engine.remove_volume.assert_awaited_once()

    async def test_disk_volume_substitution_is_rejected_before_container_creation(self):
        self.engine.api = AsyncMock(return_value={'Driver':'local', 'Options':{}, 'Labels':{LABEL+'.job':'job'}})
        self.engine.remove = AsyncMock()
        self.engine.exec_stream = AsyncMock()
        result = await self.engine.execute('job', 'result=1', {}, [], asyncio.Event())
        self.assertEqual(result['execution_status'], 'isolation_check_failed')
        self.assertEqual(self.engine.api.call_count, 1)
        self.engine.exec_stream.assert_not_awaited()
        self.engine.remove_volume.assert_awaited_once_with('enzymind-python-job')

    async def test_volume_cleanup_failure_is_not_reported_as_success(self):
        self.engine.api = AsyncMock(side_effect=httpx.ReadError('volume create response lost'))
        self.engine.remove = AsyncMock()
        self.engine.remove_volume = AsyncMock(side_effect=httpx.ReadError('volume delete failed'))
        result = await self.engine.execute('job', 'result=1', {}, [], asyncio.Event())
        self.assertEqual(result['execution_status'], 'cleanup_failed')


if __name__ == '__main__':
    unittest.main()
