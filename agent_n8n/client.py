"""Notebook-compatible EnzyMind client for the persistent Agent workspace.

Existing ``EnzyMindN8NClient().chat(...)`` calls use the current public gateway.
An explicit ``webhook_url`` or ``mode='legacy'`` retains the old n8n protocol.
"""
import codecs
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import requests

from agent_n8n.legacy_client import LegacyWebhookClient, _in_notebook
from gateway.result_catalog import normalize_result_links, RESULT_UUID


class EnzyMindAPIError(RuntimeError):
    """An API failure, including daily_limit (402), with safe structured details."""
    def __init__(self, message, status_code=None, code=None, quota=None):
        super().__init__(message)
        self.status_code, self.code, self.quota = status_code, code, quota


def _uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Expected a valid session, turn, result or request UUID.') from None


def _read_state(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('The workspace access file must contain a JSON object.')
    return data


def _write_private(path, data, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write('\n')


def _sse(response):
    """Handle UTF-8 and CRLF boundaries without splitting SSE events early."""
    def lines():
        decoder = codecs.getincrementaldecoder('utf-8')()
        pending = ''
        for chunk in response.iter_content(chunk_size=1024):
            pending += decoder.decode(chunk)
            while '\n' in pending:
                line, pending = pending.split('\n', 1)
                yield line.removesuffix('\r')
            if len(pending) > 2_000_000:
                raise EnzyMindAPIError('The Agent stream exceeded its line size limit.')
        pending += decoder.decode(b'', final=True)
        if pending:
            yield pending.removesuffix('\r')
    event, data, size = 'message', [], 0
    for line in lines():
        if line == '':
            if data:
                yield event, json.loads('\n'.join(data))
            event, data, size = 'message', [], 0
        elif line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].lstrip(' '))
            size += len(data[-1])
            if size > 2_000_000:
                raise EnzyMindAPIError('The Agent stream exceeded its frame size limit.')
    if data:
        yield event, json.loads('\n'.join(data))


class EnzyMindN8NClient(LegacyWebhookClient):
    DEFAULT_BASE_URL = 'https://cadd.zju.edu.cn/enzymind/api'
    BACKUP_BASE_URL = None

    def __init__(self, base_url=None, user_id=None, timeout=300, auto_display=True,
                 webhook_url=None, *, mode='auto', workspace_key=None,
                 workspace_file=None, session_id=None, deepseek_api_key=None,
                 backup_base_url=None, poll_interval=1):
        if mode not in ('auto', 'workspace', 'legacy'):
            raise ValueError("mode must be 'auto', 'workspace' or 'legacy'.")
        inferred_legacy = webhook_url is not None or (base_url and urlsplit(base_url).port == 5678)
        self.mode = 'legacy' if mode == 'legacy' or (mode == 'auto' and inferred_legacy) else 'workspace'
        if self.mode == 'legacy':
            if workspace_key or deepseek_api_key or session_id:
                raise ValueError('Workspace access, sessions and BYOK require mode="workspace".')
            super().__init__(base_url or 'http://localhost:5678', user_id, timeout, auto_display, webhook_url)
            return
        if webhook_url is not None:
            raise ValueError('webhook_url is only supported in legacy mode.')
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError('timeout and poll_interval must be positive.')
        self.base_url = self._base(base_url or os.getenv('ENZYMIND_BASE_URL') or self.DEFAULT_BASE_URL)
        if backup_base_url is None and self.base_url == self.DEFAULT_BASE_URL:
            backup_base_url = self.BACKUP_BASE_URL
        self.backup_base_url = self._base(backup_base_url) if backup_base_url else None
        self._active_base = self.base_url
        self.timeout, self.poll_interval, self.auto_display = timeout, poll_interval, auto_display
        self._in_notebook = _in_notebook()
        self._http = requests.Session()
        self.webhook_url = None
        self.workspace_file = Path(workspace_file or os.getenv('ENZYMIND_WORKSPACE_FILE') or
                                   Path.home() / '.local/share/enzymind/notebook-workspace.json').expanduser()
        state = _read_state(self.workspace_file)
        provided = workspace_key or os.getenv('ENZYMIND_WORKSPACE_KEY')
        if provided:
            self._workspace_key = provided
        else:
            if not state.get('access_key'):
                state.update(application='EnzyMind workspace', access_key=secrets.token_hex(32))
                try:
                    _write_private(self.workspace_file, state, exclusive=not self.workspace_file.exists())
                except FileExistsError:
                    state = _read_state(self.workspace_file)
            self._workspace_key = state['access_key']
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', self._workspace_key):
            raise ValueError('Invalid workspace access key; import an EnzyMind workspace access file.')
        self.user_id = user_id or session_id or str(uuid.uuid4())
        self.session_id = _uuid(session_id) if session_id else state.get('conversations', {}).get(self._alias())
        if self.session_id:
            self.session_id = _uuid(self.session_id)
        self._deepseek_key = None
        self.set_deepseek_key(deepseek_api_key)
        self.last_turn = None
        self.last_turn_id = None
        self.last_request_id = None
        self.partial_output = ''
        self.stream_updates = 0
        self._pending = None

    @staticmethod
    def _base(value):
        parsed = urlsplit(value.rstrip('/'))
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Use an HTTP(S) API base URL without credentials, query or fragment.')
        return value.rstrip('/')

    def _alias(self):
        canonical = self.DEFAULT_BASE_URL if self.base_url in (self.DEFAULT_BASE_URL, self.BACKUP_BASE_URL) else self.base_url
        return hashlib.sha256(json.dumps([canonical, self._workspace_key, self.user_id]).encode()).hexdigest()

    def _remember_session(self):
        state = _read_state(self.workspace_file)
        state.setdefault('conversations', {})[self._alias()] = self.session_id
        # An explicit/environment key stays in memory; never copy it into state.
        temporary = self.workspace_file.with_name(self.workspace_file.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            _write_private(temporary, state, exclusive=True)
            temporary.replace(self.workspace_file)
        finally:
            temporary.unlink(missing_ok=True)

    def set_deepseek_key(self, token):
        """Keep a personal DeepSeek key only in memory; None forgets it."""
        if self.mode == 'legacy':
            raise ValueError('BYOK requires workspace mode.')
        if token is not None and (not isinstance(token, str) or not 8 <= len(token) <= 512 or any(c.isspace() for c in token)):
            raise ValueError('Enter a valid DeepSeek API token.')
        if token and any(urlsplit(base).scheme != 'https' and urlsplit(base).hostname not in ('localhost', '127.0.0.1', '::1') for base in (self.base_url, self.backup_base_url) if base):
            raise ValueError('Use HTTPS for a personal API token outside localhost.')
        self._deepseek_key = token

    def _request(self, method, path, *, body=None, streaming=False, idempotent=False, model_key=False):
        headers = {'X-Enzymind-Client': self._workspace_key, 'Accept-Encoding': 'identity'}
        if streaming:
            headers['Accept'] = 'text/event-stream'
        if model_key and self._deepseek_key:
            headers['X-DeepSeek-API-Key'] = self._deepseek_key
        bases = [self._active_base]
        if method == 'GET' or idempotent:
            bases += [b for b in (self.base_url, self.backup_base_url) if b and b not in bases]
        for index, base in enumerate(bases):
            try:
                response = self._http.request(method, base + '/workspace' + path, json=body,
                    headers=headers, timeout=(min(15, self.timeout), min(30, self.timeout)),
                    stream=streaming, allow_redirects=False)
            except requests.RequestException:
                if index + 1 < len(bases):
                    continue
                raise EnzyMindAPIError('Cannot reach EnzyMind. A submitted turn may still be running; use resume_turn() or retry the same message/request_id, not a new calculation.') from None
            if response.status_code >= 500 and index + 1 < len(bases):
                response.close()
                continue
            if not 200 <= response.status_code < 300:
                try:
                    detail = response.json().get('detail', {})
                except (ValueError, AttributeError):
                    detail = {}
                response.close()
                message = detail.get('message') if isinstance(detail, dict) else detail if isinstance(detail, str) else None
                # Never include raw request headers or provider error bodies.
                message = message or f'EnzyMind returned HTTP {response.status_code}.'
                for secret in (self._workspace_key, self._deepseek_key):
                    if secret:
                        message = message.replace(secret, '[redacted]')
                raise EnzyMindAPIError(message, response.status_code,
                    detail.get('code') if isinstance(detail, dict) else None,
                    detail.get('quota') if isinstance(detail, dict) else None)
            self._active_base = base
            return response

    def _json(self, method, path, **kwargs):
        with self._request(method, path, **kwargs) as response:
            return response.json()

    def usage(self):
        return self._json('GET', '/usage')

    def get_session(self):
        if not self.session_id:
            raise ValueError('No conversation yet; call chat() first or supply session_id.')
        return self._json('GET', '/sessions/' + _uuid(self.session_id))

    def get_turn(self, turn_id=None):
        return self._json('GET', '/turns/' + _uuid(turn_id or self.last_turn_id))

    def cancel_turn(self, turn_id=None):
        """Explicitly stop a turn; already submitted scientific jobs may finish."""
        turn = self._json('POST', '/turns/' + _uuid(turn_id or self.last_turn_id) + '/cancel',
                          body={}, idempotent=True)
        if turn.get('id') == self.last_turn_id:
            self.last_turn, self._pending = turn, None
        return turn

    def get_result(self, result_id):
        return self._json('GET', '/results/' + _uuid(result_id))

    def list_results(self):
        return self._json('GET', '/results')['results']

    def export_result(self, result_id, path):
        """Download a full result now; server results expire after 90 days."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.get_result(result_id), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return target

    def export_access(self, path):
        """Explicit private export for the website's Workspace access → Import."""
        target = Path(path)
        _write_private(target, {'application': 'EnzyMind workspace', 'access_key': self._workspace_key}, exclusive=True)
        return target

    def _markdown(self, text):
        # Never invent an ID to repair an unresolvable placeholder.
        text = normalize_result_links(text, {})
        origin = urlsplit(self.base_url)
        return re.sub(r'(?<![\w:/])(/enzymind/results/' + RESULT_UUID + r')',
                      lambda m: f'{origin.scheme}://{origin.netloc}' + m.group(1), text, flags=re.I)

    def chat(self, message, fasta_file=None, display=True, stream=None,
             on_tool_start=None, on_tool_end=None, *, references=None,
             request_id=None, on_update=None):
        if self.mode == 'legacy':
            if references or request_id or on_update:
                raise ValueError('Saved result references/request IDs require workspace mode.')
            return super().chat(message, fasta_file, display, stream, on_tool_start, on_tool_end)
        if not isinstance(message, str) or not message.strip():
            raise ValueError('Enter a non-empty message.')
        if fasta_file is not None:
            path = Path(fasta_file)
            if path.stat().st_size > 96_000:
                raise ValueError('FASTA file is too large for an Agent question; use fewer records.')
            content = path.read_text(encoding='utf-8-sig')
            if not content.lstrip().startswith('>'):
                raise ValueError('The attachment must be a FASTA file with named records.')
            message += f'\n\nAttached FASTA file: {path.name}\n\n{content}'
        message = message.strip()
        if len(message) > 24000:
            raise ValueError('Message and FASTA must fit within 24,000 characters. Records are never concatenated or silently truncated.')
        refs = list(dict.fromkeys(_uuid(r) for r in (references or [])))
        if len(refs) > 4:
            raise ValueError('Attach up to four saved results.')
        if not self.session_id:
            self.usage()  # Select a reachable gateway before a non-idempotent session POST.
            self.session_id = _uuid(self._json('POST', '/sessions', body={})['id'])
            self._remember_session()
        fingerprint = json.dumps([self.session_id, message, refs], ensure_ascii=False)
        if self._pending and self._pending[0] != fingerprint:
            raise EnzyMindAPIError('The previous turn is unresolved. Use resume_turn() before submitting a different question.')
        rid = _uuid(request_id) if request_id else self._pending[1] if self._pending else str(uuid.uuid4())
        if self._pending and rid != self._pending[1]:
            raise EnzyMindAPIError('The previous request is unresolved. Resume it before changing request_id.')
        self._pending = (fingerprint, rid)
        self.last_request_id = rid
        try:
            turn = self._json('POST', f'/sessions/{self.session_id}/turns',
                body={'message': message, 'references': refs, 'request_id': rid}, idempotent=True, model_key=True)
        except EnzyMindAPIError as exc:
            if exc.status_code and exc.status_code < 500:
                self._pending = None  # Validation/quota rejection did not accept this request.
            raise
        self.last_turn_id = turn['id']
        return self._wait(turn, display, self._in_notebook if stream is None else stream, on_tool_start, on_tool_end, on_update)

    def resume_turn(self, turn_id=None, *, display=True, stream=True,
                    on_tool_start=None, on_tool_end=None, on_update=None):
        """Resume an existing turn by GET only; never submit a duplicate calculation."""
        if not turn_id and not self.last_turn_id and self._pending:
            match = next((t for t in self.get_session()['turns'] if t['request_id'] == self._pending[1]), None)
            if not match:
                raise EnzyMindAPIError('No saved turn matches the pending request. Retry the same message/request_id.')
            turn_id = match['id']
        turn = self.get_turn(turn_id)
        self.session_id, self.last_turn_id = turn['session_id'], turn['id']
        self.last_request_id = turn.get('request_id', self.last_request_id)
        return self._wait(turn, display, stream, on_tool_start, on_tool_end, on_update)

    def _wait(self, turn, display, stream, on_start, on_end, on_update):
        deadline = time.monotonic() + self.timeout
        self.last_turn = turn
        self.partial_output, self.stream_updates = '', 0
        handle = None
        if display and self.auto_display and self._in_notebook:
            from IPython.display import display as ipy_display, Markdown
            handle = ipy_display(Markdown('*Waiting for EnzyMind…*'), display_id=True)
        seen, counts, previous = set(), {'tool_start': 0, 'tool_end': 0}, ''

        def update(current):
            nonlocal previous
            self.last_turn = current
            for event in current.get('events', []):
                identity = event.get('seq', json.dumps(event, sort_keys=True))
                if identity in seen:
                    continue
                seen.add(identity)
                kind = event.get('kind')
                if kind in counts:
                    counts[kind] += 1
                    callback = on_start if kind == 'tool_start' else on_end
                    if callback:
                        callback(counts[kind])
            text = current.get('output', '') if current['status'] == 'completed' else current.get('partial_output', '')
            self.partial_output = text
            if text == previous:
                return
            previous = text
            if current['status'] in ('running', 'queued') and text:
                self.stream_updates += 1
            rendered = self._markdown(text)
            if handle:
                handle.update(Markdown(rendered))
            elif display and self.auto_display and not self._in_notebook and current['status'] == 'completed':
                print(rendered)
            if on_update:
                on_update(rendered)

        update(turn)
        try:
            if stream and turn['status'] in ('running', 'queued'):
                try:
                    with self._request('GET', f'/turns/{turn["id"]}/stream', streaming=True) as response:
                        if 'text/event-stream' not in response.headers.get('Content-Type', ''):
                            raise ValueError('Not an SSE response')
                        for event, data in _sse(response):
                            if time.monotonic() >= deadline:
                                raise TimeoutError('Agent wait timed out; call resume_turn() to read the existing task.')
                            if event in ('snapshot', 'done'):
                                turn = data['turn']
                            elif event == 'delta':
                                turn = {**turn, 'partial_output': turn.get('partial_output', '') + data['text']}
                            elif event == 'progress':
                                latest = {**turn, **data}
                                # Terminal progress announces completion but does
                                # not contain the final output/memory transaction.
                                # Read the saved turn before accepting it as final.
                                if latest['status'] not in ('running', 'queued'):
                                    latest = self.get_turn(turn['id'])
                                turn = latest
                            else:
                                continue
                            update(turn)
                            if turn['status'] not in ('running', 'queued'):
                                break
                except (requests.RequestException, EnzyMindAPIError, ValueError):
                    pass  # Reconcile via GET; never replay the POST after a stream interruption.
            while turn['status'] in ('running', 'queued'):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Agent wait timed out; call resume_turn() to read the existing task.')
                turn = self.get_turn(turn['id'])
                update(turn)
                if turn['status'] in ('running', 'queued'):
                    time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
        except (Exception, KeyboardInterrupt):
            if handle:
                handle.update(Markdown(self._markdown(self.partial_output) + '\n\n*Waiting interrupted. This is partial text; use `resume_turn()` to retrieve the saved task.*'))
            raise
        self._pending = None
        if turn['status'] != 'completed':
            if handle:
                handle.update(Markdown(self._markdown(self.partial_output) + '\n\n*Incomplete answer; not committed to conversation memory.*'))
            raise EnzyMindAPIError(turn.get('error') or f'Agent turn {turn["status"]}. Saved tool results remain available.')
        if not isinstance(turn.get('output'), str) or not turn['output'].strip():
            raise EnzyMindAPIError('The server returned an empty completion. Inspect the saved turn before submitting another task.')
        return self._markdown(turn['output'])

    def new_conversation(self):
        if self.mode == 'legacy':
            return super().new_conversation()
        if self._pending:
            raise EnzyMindAPIError('Resolve the current turn before starting another conversation.')
        self.user_id, self.session_id = str(uuid.uuid4()), None
        self.last_turn = self.last_turn_id = self.last_request_id = None
        return self.user_id

    def close(self):
        if self.mode == 'workspace':
            self._deepseek_key = None
            self._http.close()

    def __repr__(self):
        return f'EnzyMindN8NClient(mode={self.mode!r}, user_id={self.user_id!r})'


def quick_chat(message, base_url=None, **kwargs):
    client = EnzyMindN8NClient(base_url=base_url, **kwargs)
    try:
        return client.chat(message)
    finally:
        client.close()
