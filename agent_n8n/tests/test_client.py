import io
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock

import pytest
import requests
from urllib3.response import HTTPResponse

from agent_n8n.client import EnzyMindN8NClient, EnzyMindAPIError

SID, TID, RID = (str(uuid4()) for _ in range(3))
KEY = 'a' * 64
TOKEN = 'sk-personal-test-only'


def response(data, status=200, content_type='application/json'):
    r = requests.Response()
    r.status_code = status
    r.headers['Content-Type'] = content_type
    r._content = json.dumps(data, ensure_ascii=False).encode()
    r._content_consumed = True
    r.encoding = 'utf-8'
    return r


def turn(status='completed', **changes):
    return {'id': TID, 'session_id': SID, 'status': status, 'partial_output': '',
            'output': 'Verified answer' if status == 'completed' else '', 'events': [], **changes}


def stream(frames):
    body = ': keepalive\r\n\r\n' + ''.join('event: ' + event + '\r\ndata: ' + json.dumps(data, ensure_ascii=False) + '\r\n\r\n' for event, data in frames)
    r = requests.Response()
    r.status_code = 200
    r.headers['Content-Type'] = 'text/event-stream; charset=utf-8'
    r.raw = HTTPResponse(body=io.BytesIO(body.encode('utf-8')), preload_content=False)
    return r


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('ENZYMIND_WORKSPACE_KEY', raising=False)
    monkeypatch.delenv('ENZYMIND_BASE_URL', raising=False)
    return EnzyMindN8NClient(workspace_key=KEY, workspace_file=tmp_path/'state.json',
                            session_id=SID, auto_display=False, poll_interval=.001)


def test_default_identity_persists_and_new_conversation_keeps_quota_identity(tmp_path, monkeypatch):
    monkeypatch.delenv('ENZYMIND_WORKSPACE_KEY', raising=False)
    path = tmp_path/'private'/'access.json'
    first = EnzyMindN8NClient(workspace_file=path)
    second = EnzyMindN8NClient(workspace_file=path)
    before = second._workspace_key
    second.new_conversation()
    assert before == first._workspace_key == second._workspace_key
    assert path.stat().st_mode & 0o777 == 0o600
    assert first.base_url == 'https://cadd.zju.edu.cn/enzymind/api'
    assert first.backup_base_url is None
    assert before not in repr(first)


def test_sse_utf8_progress_callbacks_final_citations_and_silent_display(client, monkeypatch, capsys):
    starts, ends, updates = [], [], []
    events = [{'seq':1, 'kind':'tool_start','data':{'tool':'check'}},
              {'seq':2, 'kind':'tool_end','data':{'tool':'check','status':'completed'}}]
    result = turn(output=f'酶🧬 [Evidence](/enzymind/results/{RID}) [Unknown](https://example.invalid/)', events=events)
    frames = [('snapshot', {'turn':turn('running')}), ('delta', {'text':'酶'}),
              ('progress', {'status':'running','events':events}), ('delta', {'text':'🧬'}),
              ('snapshot', {'turn':turn('running', partial_output='酶🧬', events=events)}),
              ('done', {'turn':result})]
    calls=[]
    def send(method, url, **kwargs):
        calls.append((method,url,kwargs))
        return response(turn('running')) if method=='POST' else stream(frames)
    monkeypatch.setattr(client._http, 'request', send)
    answer=client.chat('Check annotation', stream=True, display=False,
                       on_tool_start=starts.append, on_tool_end=ends.append, on_update=updates.append)
    assert starts == ends == [1]
    assert '酶🧬' in answer and 'example.invalid' not in answer
    assert f'https://cadd.zju.edu.cn/enzymind/results/{RID}' in answer
    assert client.last_turn['output'] == result['output']
    assert client.stream_updates == 2
    assert updates[:2] == ['酶','酶🧬']
    assert capsys.readouterr().out == ''
    assert [c[0] for c in calls] == ['POST','GET']


def test_interrupted_stream_polls_saved_turn_without_reposting(client, monkeypatch):
    methods=[]
    def send(method,url,**kwargs):
        methods.append(method)
        if method=='POST':return response(turn('running'))
        if url.endswith('/stream'):return stream([('snapshot',{'turn':turn('running',partial_output='Partial')})])
        return response(turn(output='Saved final answer'))
    monkeypatch.setattr(client._http,'request',send)
    assert client.chat('Question',stream=True,display=False) == 'Saved final answer'
    assert methods == ['POST','GET','GET']


@pytest.mark.parametrize('status',['failed','cancelled','interrupted'])
def test_partial_answer_never_becomes_success(client,monkeypatch,status):
    monkeypatch.setattr(client._http,'request',lambda *a,**kw:response(turn(status,partial_output='Partial',error='Upstream unavailable')))
    with pytest.raises(EnzyMindAPIError,match='Upstream unavailable'):
        client.chat('Question',stream=True,display=False)
    assert client.last_turn['status']==status
    assert client.partial_output=='Partial'


def test_post_failover_keeps_request_id_and_payload(client,monkeypatch):
    client.backup_base_url = 'https://backup.example.org/enzymind/api'
    calls=[]
    def send(method,url,**kwargs):
        calls.append((url,kwargs))
        if len(calls)==1:raise requests.ConnectionError('response lost after commit')
        return response(turn())
    monkeypatch.setattr(client._http,'request',send)
    assert client.chat('Question',stream=False,display=False)=='Verified answer'
    assert len(calls)==2 and calls[0][0]!=calls[1][0]
    assert calls[0][1]['json']==calls[1][1]['json']
    assert calls[0][1]['allow_redirects'] is False
    assert 'verify' not in calls[0][1]  # requests keeps certificate validation on.


def test_lost_submit_can_resume_by_request_id_without_another_post(client,monkeypatch):
    calls=[]
    def fail(method,url,**kwargs):
        calls.append(method)
        raise requests.ConnectionError('lost')
    monkeypatch.setattr(client._http,'request',fail)
    with pytest.raises(EnzyMindAPIError):client.chat('Question',display=False)
    request_id=client.last_request_id
    with pytest.raises(EnzyMindAPIError,match='unresolved'):client.chat('Different question',display=False)
    def recover(method,url,**kwargs):
        assert method=='GET'
        if '/sessions/' in url:return response({'turns':[turn(request_id=request_id)]})
        return response(turn())
    monkeypatch.setattr(client._http,'request',recover)
    assert client.resume_turn(display=False)=='Verified answer'
    assert client._pending is None and len(calls)==1


def test_quota_and_byok_do_not_leak_keys_or_fallback_billing(client,monkeypatch):
    sent=[]
    def send(method,url,**kw):
        sent.append((method,url,kw))
        if method=='GET':return response({'remaining':0})
        if kw['headers'].get('X-DeepSeek-API-Key'):return response(turn(billing_mode='byok'))
        return response({'detail':{'code':'daily_limit','message':'Daily allowance exhausted','quota':{'remaining':0}}},402)
    monkeypatch.setattr(client._http,'request',send)
    with pytest.raises(EnzyMindAPIError) as exc:client.chat('Question',display=False)
    assert exc.value.status_code==402 and exc.value.code=='daily_limit' and exc.value.quota['remaining']==0
    client.set_deepseek_key(TOKEN)
    client.usage()
    assert client.chat('Question',display=False)=='Verified answer'
    assert 'X-DeepSeek-API-Key' not in sent[-2][2]['headers']
    assert sent[-1][2]['headers']['X-DeepSeek-API-Key']==TOKEN
    assert TOKEN not in repr(client) and TOKEN not in json.dumps(client.last_turn)
    client.close()
    assert client._deepseek_key is None


def test_named_fasta_records_and_references_are_preserved(client,tmp_path,monkeypatch):
    path=tmp_path/'two.fasta';content='>first\nACDE\n>second\nMKWV\n';path.write_text(content)
    sent=[]
    monkeypatch.setattr(client._http,'request',lambda method,url,**kw:sent.append(kw) or response(turn()))
    client.chat('Inspect attached records',fasta_file=path,references=[RID,RID],display=False,stream=False)
    assert sent[0]['json']['message'].endswith(content.rstrip())
    assert sent[0]['json']['references']==[RID]
    path.write_text('>long\n'+'A'*25000)
    with pytest.raises(ValueError,match='24,000'):client.chat('Inspect',fasta_file=path)
    assert len(sent)==1


def test_alias_and_session_resume_with_persistent_key_without_network(tmp_path,monkeypatch):
    path=tmp_path/'access.json'
    monkeypatch.delenv('ENZYMIND_WORKSPACE_KEY',raising=False)
    first=EnzyMindN8NClient(workspace_file=path,user_id='my-study',auto_display=False)
    def send(method,url,**kw):
        if url.endswith('/usage'):return response({'remaining':10})
        if url.endswith('/sessions'):return response({'id':SID})
        return response(turn())
    monkeypatch.setattr(first._http,'request',send)
    first.chat('Question',stream=False,display=False)
    second=EnzyMindN8NClient(workspace_file=path,user_id='my-study')
    assert second.session_id==first.session_id==SID
    third=EnzyMindN8NClient(workspace_file=path,workspace_key='b'*64,user_id='my-study')
    assert third.session_id is None
    explicit=EnzyMindN8NClient(workspace_file=path,session_id=SID)
    assert explicit.session_id==SID


def test_explicit_legacy_webhook_keeps_original_protocol(monkeypatch):
    url='http://localhost:5678/webhook/old-test'
    client=EnzyMindN8NClient(webhook_url=url,user_id='legacy-user',auto_display=False)
    sent=[]
    r=response(None);r._content=b'{"type":"item","content":"Legacy answer"}\n'
    monkeypatch.setattr(requests,'post',lambda destination,**kw:sent.append((destination,kw)) or r)
    assert client.chat('Question',stream=False,display=False)=='Legacy answer'
    assert sent[0][0]==url
    assert sent[0][1]['json']=={'userID':'legacy-user','message':'Question'}
    assert 'X-Enzymind-Client' not in sent[0][1]['headers']


def test_private_export_is_browser_compatible_and_result_export_contains_no_credentials(client,tmp_path,monkeypatch):
    access=client.export_access(tmp_path/'access.json')
    assert json.loads(access.read_text())=={'application':'EnzyMind workspace','access_key':KEY}
    assert access.stat().st_mode & 0o777==0o600
    monkeypatch.setattr(client._http,'request',lambda *a,**kw:response({'id':RID,'payload':{'ec_number':'3.2.1.17'}}))
    result=client.export_result(RID,tmp_path/'result.json')
    assert '3.2.1.17' in result.read_text() and KEY not in result.read_text()


def test_no_ipython_is_required_for_plain_python(monkeypatch):
    import builtins
    from agent_n8n.legacy_client import _in_notebook
    original=builtins.__import__
    def optional(name,*a,**kw):
        if name=='IPython':raise ImportError('not installed')
        return original(name,*a,**kw)
    monkeypatch.setattr(builtins,'__import__',optional)
    assert _in_notebook() is False


def test_timeout_keeps_turn_resumable_and_does_not_resubmit(client,monkeypatch):
    import time
    client.timeout=.001
    methods=[]
    def send(method,url,**kw):
        methods.append(method)
        if method=='GET':time.sleep(.005)
        return response(turn('running'))
    monkeypatch.setattr(client._http,'request',send)
    with pytest.raises(TimeoutError,match='resume_turn'):
        client.chat('Question',stream=False,display=False)
    assert client.last_turn_id==TID and methods.count('POST')==1
    monkeypatch.setattr(client._http,'request',lambda method,*a,**kw:response(turn()) if method=='GET' else pytest.fail('No resubmission'))
    assert client.resume_turn(display=False)=='Verified answer'


def test_unresolved_request_rejects_new_request_id_and_cancel_preserves_identity(client,monkeypatch):
    client._pending=(json.dumps([SID,'Question',[]],ensure_ascii=False),str(uuid4()))
    with pytest.raises(EnzyMindAPIError,match='changing request_id'):
        client.chat('Question',request_id=str(uuid4()),display=False)
    client.last_turn_id=TID
    monkeypatch.setattr(client._http,'request',lambda method,url,**kw:response(turn('cancelled')))
    assert client.cancel_turn()['status']=='cancelled'
    assert client._pending is None
    assert client._workspace_key==KEY


def test_notebook_display_is_updated_in_place_and_disable_really_disables_it(client,monkeypatch):
    import sys,types
    shown=[]
    handle=Mock()
    display_module=types.ModuleType('IPython.display')
    display_module.Markdown=lambda value:value
    display_module.display=lambda value,**kw:shown.append(value) or handle
    monkeypatch.setitem(sys.modules,'IPython.display',display_module)
    client._in_notebook=True;client.auto_display=True
    monkeypatch.setattr(client._http,'request',lambda *a,**kw:response(turn()))
    client.chat('Question',stream=True)
    assert len(shown)==1
    handle.update.assert_called_once_with('Verified answer')
    client.chat('Another question',display=False,stream=True)
    assert len(shown)==1 and handle.update.call_count==1


def test_sse_parser_keeps_multibyte_characters_split_between_network_chunks():
    from agent_n8n.client import _sse
    data='event: delta\r\ndata: {"text":"酶🧬"}\r\n\r\n'.encode()
    response=Mock()
    response.iter_content.return_value=[data[i:i+1] for i in range(len(data))]
    assert list(_sse(response))==[('delta',{'text':'酶🧬'})]


def test_terminal_progress_is_not_mistaken_for_final_answer(client,monkeypatch):
    methods=[]
    def send(method,url,**kw):
        methods.append((method,url))
        if method=='POST':return response(turn('running'))
        if url.endswith('/stream'):
            return stream([('snapshot',{'turn':turn('running')}),('delta',{'text':'Partial'}),
                           ('progress',{'status':'completed','error':None,'events':[]}),
                           ('done',{'turn':turn(output='Full saved answer')})])
        return response(turn(output='Full saved answer'))
    monkeypatch.setattr(client._http,'request',send)
    assert client.chat('Question',stream=True,display=False)=='Full saved answer'
    assert sum(method=='POST' for method,_ in methods)==1
    assert methods[-1][1].endswith('/turns/'+TID)


def test_empty_completion_is_not_accepted_as_success(client,monkeypatch):
    monkeypatch.setattr(client._http,'request',lambda *a,**kw:response(turn(output='')))
    with pytest.raises(EnzyMindAPIError,match='empty completion'):
        client.chat('Question',display=False)
