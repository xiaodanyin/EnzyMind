# EnzyMind Agent Python / Jupyter client

`EnzyMindN8NClient` uses the website's persistent Workspace API by default. It supports streaming, session recovery, saved-result citations, a default daily allowance of 10 successful turns and personal DeepSeek tokens. The existing class name, `chat()` arguments and string return value remain compatible; archived notebooks and saved outputs do not need rewriting.

See [Workspace v2](workspace/README.md) for service deployment and n8n workflow configuration. The Jupyter client needs no n8n management API key and should not call the internal workflow webhook directly.

## Installation and imports

Use Python 3.9+. From the repository root, install into the selected notebook environment:

```bash
python -m pip install -r agent_n8n/requirements-notebook.txt
```

Ordinary Python scripts only need `requirements-client.txt`. Notebooks running from `tests/` can retain this import pattern:

```python
import sys
sys.path.append('../')
from agent_n8n.client import EnzyMindN8NClient

client = EnzyMindN8NClient()
response = client.chat('Retrieve enzyme annotations and catalytic reactions for P00761, citing the saved results.')
```

The default API URL is `https://cadd.zju.edu.cn/enzymind/api/`, with no automatic fallback to other domains. A custom URL must include the API prefix, for example `base_url='http://localhost:8080/api'`. Set `backup_base_url` explicitly to use a backup deployment.

## Workspaces, memory and recovery

The default private identity file is `~/.local/share/enzymind/notebook-workspace.json`, with permissions `0600`. Creating a client or calling `new_conversation()` starts a conversation while retaining the workspace identity and daily allowance. `user_id` is a local conversation alias; `client.session_id` is the actual server session ID. The same identity file, alias and deployment can restore the same session.

```python
client = EnzyMindN8NClient(user_id='my-study')
answer = client.chat('Retrieve enzyme annotations for P00761.')
answer = client.chat('Reuse the saved result to report its EC number without repeating the calculation.')

session_id = client.session_id
restored = EnzyMindN8NClient(session_id=session_id)
restored.get_session()  # Original conversation, memory summary and session results
```

Set `workspace_file=...` or `ENZYMIND_WORKSPACE_FILE` to select the private identity file. Alternatively, supply `workspace_key=...` or `ENZYMIND_WORKSPACE_KEY`; an explicit key is not automatically written to the identity file. Do not save access keys in notebook source, outputs or Git.

Results are retained for 90 days. Returned Markdown uses absolute website links that can be opened from Jupyter. The browser needs the same workspace identity to view private results. Export the access file explicitly, then import it through **Workspace access → Import** on the website:

```python
# Private file: do not commit or share it. Existing files are not overwritten.
client.export_access('/private/path/enzymind-workspace-access.json')

# Export complete scientific records for archiving; exports contain no access key.
records = client.get_session()['results']
client.export_result(records[0]['id'], '/my/results/result.json')
```

## Streaming, FASTA and tool events

Jupyter streams Markdown by default. `stream=False` polls for the completed answer. `display=False` or `auto_display=False` disables automatic display, including streamed display.

```python
client.chat('Analyze the attached records.', fasta_file='proteins.fasta', stream=True,
            on_tool_start=lambda index: print('Started tool', index),
            on_tool_end=lambda index: print('Finished tool', index))

# on_update receives the complete current Markdown, not a delta to concatenate.
client.chat('Explain the saved result.', references=[records[0]['id']],
            display=False, on_update=lambda text: None)
```

FASTA inputs retain each record's name and sequence without concatenation or silent truncation. This client currently caps the combined message and attachment at 24,000 characters, with at most four result references per turn. The web composer and Gateway have a separate 300,000-character limit.

If SSE disconnects, the client resumes reading the existing turn without resubmitting calculations. A timeout or interrupted notebook wait does not cancel the server task:

```python
client.resume_turn()  # Read-only recovery using last_turn_id or the original request_id
# Another process can resume with the same workspace identity:
restored.resume_turn(saved_turn_id)
# To stop explicitly: client.cancel_turn()
```

`client.last_turn` includes status, events and raw server output; `partial_output` may be incomplete. Failure, cancellation or interruption raises `EnzyMindAPIError` instead of returning partial text as a successful answer. The same explicit `request_id`, session and input retrieve the existing request idempotently. A backup endpoint reuses the request ID to avoid duplicate computation.

## Daily allowance and personal DeepSeek tokens

```python
client.usage()
from getpass import getpass
client.set_deepseek_key(getpass('DeepSeek API token: '))
client.chat('Continue the analysis.')
client.set_deepseek_key(None)  # Forget the token
```

Personal tokens remain in memory and are sent only when submitting a turn. Exhausted allowance raises `EnzyMindAPIError` with `status_code == 402`, `code == 'daily_limit'` and `quota`. The client neither creates a new identity to bypass the allowance nor silently switches billing modes.

## Explicit legacy webhook compatibility

Existing n8n workflows remain callable through the original `userID/message` and multipart FASTA protocol:

```python
legacy = EnzyMindN8NClient(
    webhook_url='http://localhost:5678/webhook/your-existing-webhook-id',
    user_id='original-study',
)
legacy.chat('Retrieve enzyme information.')

# A custom legacy n8n root URL requires explicit legacy mode.
legacy = EnzyMindN8NClient(base_url='https://your-n8n-host', mode='legacy')
```

An explicit `webhook_url` or an older address on port `5678` selects legacy mode. It uses the original workflow and memory mechanism, without Workspace v2 allowance, result-library or session-recovery features. The default constructor uses the website Gateway. Histories are not automatically migrated or merged between modes.

## Validation and archives

- Workspace notebook: [test_agent_workspace_v2_20261111.ipynb](../tests/test_agent_workspace_v2_20261111.ipynb). The recorded validation covers streaming, non-streaming follow-ups, identity/session recovery, FASTA, multiple result references and downloads.
- The 18 original notebooks retain their source and saved outputs. Archived SHA-256 checksums are listed in the [archive manifest](../tests/notebook_archive_manifest_20261111.json).
- Protocol tests: `python -m pytest agent_n8n/tests/test_client.py -q`. These cover stream recovery, Unicode, legacy compatibility, allowance, identity isolation and idempotency without executing historical notebooks.
