# EnzyMind Agent Workspace v2

The workspace follows the persistent-memory and saved-evidence architecture of **EasIFA Agent Workspace v2 · persistent memory & results**. The gateway stores conversations, tool events, complete scientific results and structure snapshots. n8n plans the analysis, calls existing EnzyMind services, compresses older conversation context and returns a cited answer. The former unmetered public chat endpoint returns HTTP 410 with the workspace URL; existing n8n workflows remain untouched.

## Start and install

1. Run the gateway from the repository root with a **single worker**:

   ```bash
   gateway/venv/bin/python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8080
   ```

2. Generate `enzymind_workspace_v2.json` with `python3 agent_n8n/workspace/build_workflow.py`. The template contains no credentials. Use the official n8n management API to copy EasIFA's existing **Research language model** DeepSeek binding and create an EnzyMind-only temporary relay credential:

   ```bash
   # The installer prompts for the management key without echo or persistence.
   python3 agent_n8n/workspace/deploy.py \
     --model-workflow EXISTING_EASIFA_WORKFLOW_ID \
     --model-node 'Research language model' \
     --target EXISTING_ENZYMIND_WORKSPACE_ID \
     --gateway-url http://host.docker.internal:8080 \
     --activate
   ```

   Omit `--target` only for the first installation. Updates require the existing workspace's ID and matching name. Wait for active EnzyMind turns to finish before updating. The source EasIFA workflow is read only; its model credential is reused by reference. The installer privately backs up the target and restores it if the update fails. Subsequent runs reuse the target's relay credential. Tool and relay URLs are literal, so n8n environment-variable access is not required. Linux Docker may need `host.docker.internal:host-gateway` in its host mappings.

   The source may use the native DeepSeek node or an Anthropic-compatible node explicitly configured for a `deepseek-*` model. The installer preserves its type, parameters and credential reference. An older deployed workspace can lack the personal-key model branch even when the Gateway and client support it; updating only a tool node does not install BYOK. Use this installer to deploy the complete billing selector, relay and response contract together.

   For manual import, bind **Research language model** to the same DeepSeek credential as EasIFA. Bind **User DeepSeek relay** to a new OpenAI-compatible credential whose API key is the expression `={{ $('Workspace Webhook').first(0,0).json.body.model_relay_token || 'inactive-request-only-relay' }}` and whose Base URL is `http://host.docker.internal:8080/api/workspace/model`. This credential contains an expression, never a user's DeepSeek key. Keep both model connections through **Select billing model**, including the summary chain.

3. Activate the workspace workflow. Its POST webhook is `/webhook/enzymind-workspace-v2`. The gateway setting `N8N_WORKSPACE_WEBHOOK_URL` defaults to `http://localhost:5678/webhook/enzymind-workspace-v2`. Configure this for your deployment topology. Keep the gateway tool endpoints reachable from n8n.

4. Run `bash scripts/start_all.sh` to start all 19 scientific services, the gateway and frontend. `start_web.sh` alone only starts the web tier. Verify real inputs with `gateway/venv/bin/python scripts/verify_api.py`; add `--predictions` to exercise prediction backends and the configured BLAST search. The UI is `/enzymind/agent`, with saved records at `/enzymind/results`. Existing reverse-proxy rules must forward `/enzymind/api/workspace/*` to gateway `/api/workspace/*`, as they do for other API paths.

## Persistence and execution

For production, copy `scripts/production.env.example` to the repository root as `.env.production`; the start scripts load it, or an explicit `ENZYMIND_ENV_FILE`. It keeps new structure outputs and retention scans inside the EnzyMind repository's ignored `files/` directory. Adapt the n8n webhook URL if needed. Do not copy a development workspace database. Normal upgrades migrate the existing workspace without resetting records. Initializing an empty workspace is only for a new installation or an explicit reset; retain scientific reference databases and other applications' databases. Update only EnzyMind's Workspace v2 workflow. The shared n8n container does not need a restart.

## Daily allowance and personal DeepSeek keys

The policy matches EasIFA: **10 successful Agent turns per browser workspace per day**, resetting at midnight in `Asia/Shanghai`. A turn can include reasoning, tools and memory compression; these internal model calls share the turn's billing mode. Scientific tool pages do not consume Agent turns. `/api/workspace/usage` is the authoritative counter. A SQLite transaction reserves an allowance before dispatch; retries with the same request ID are idempotent, while concurrent conversations share the allowance. Failures, cancellation and expired workers release reservations. Completed charges survive conversation deletion and restarts. Only two days of quota metadata are retained, separately from the 90-day research records.

After exhaustion, the UI offers a personal DeepSeek API key. Keys stay in page memory and active gateway tasks; they never enter local/session storage, SQLite, exports, n8n webhook data or n8n credentials. Refresh/navigation clears the page's key, while an active turn may finish; **Forget key** stops using it for future turns. n8n receives a random capability bound to the current turn. The gateway forwards only to the [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/) and revokes the capability when the turn ends. Both Agent and summary calls use the selected model. Invalid credentials, insufficient balance and rate limits do not fall back to the platform key. Relay calls are capped at 24 per turn and 4096 output tokens per call.

Settings: `ENZYMIND_AGENT_DAILY_LIMIT=10`, `ENZYMIND_AGENT_QUOTA_TIMEZONE=Asia/Shanghai`, `ENZYMIND_AGENT_DEEPSEEK_MODEL=deepseek-chat` (the EasIFA default). Keep a **single gateway worker** for the in-memory relay. Use HTTPS for the public site and do not configure proxies/APM to log `X-DeepSeek-API-Key` or Authorization headers. This is the same anonymous workspace identity as EasIFA; clearing browser storage creates another identity, so the allowance is not an account-based anti-abuse boundary. No external Redis or shared database is changed.

The workflow allows up to two hours for a turn. Structure requests allow the ESMFold service's default one-hour deadline plus transport overhead; ordinary scientific calls allow 15 minutes. Keep any external reverse proxy's read timeout consistent with these limits for standalone tool requests. Workspace streaming sends a keepalive every 15 seconds; reverse proxies must honor `X-Accel-Buffering: no` or disable buffering for the stream route.

- `ENZYMIND_WORKSPACE_DB` sets the SQLite location. Default: `files/workspace/workspace.sqlite3`, outside version control. Back up with SQLite's backup API, or stop the gateway before copying the database and its WAL files. Persist this directory across releases/container replacement.
- A browser generates a random access key; the database stores its SHA-256 digest. Results and conversations require that key, including downloads. This is a browser-capability workspace, not an institutional login/account system. The UI can export and restore the access file. A result URL alone grants no access. Losing both browser storage and the access file loses access to those records.
- n8n receives a separate short-lived turn capability. Tools derive the owner and EasIFA session from this capability, never from model-supplied IDs. Tool capabilities stop working when the turn finishes or is cancelled.
- A request UUID prevents duplicate submissions after uncertain network errors. Only one turn can run per conversation. The UI receives native model text and durable tool/memory progress through an authenticated SSE request, reconnecting after refresh without another prediction submission. Read-only polling remains a fallback when the stream is unavailable.
- A renewable 180-second lease is refreshed every 30 seconds, within the two-hour turn limit. Recovery interrupts only expired leases, preserving live workers and completed records. Cancellation/expired leases cannot commit late replies. A restart does **not** resume inference or resubmit predictions. Run one gateway worker; durable multi-worker job dispatch remains outside this implementation. SQLite migrations add columns without deleting old records.
- Stop cancels Agent orchestration. A previously submitted scientific computation may finish and save its result. Explicit retries are new work.
- Tools are limited to 12 calls per turn. Full results stay in storage within the 90-day retention period. Model context omits coordinate blobs, bounds arrays/strings and marks excerpts. `Read Saved Result` supports a field path and array pagination for exact follow-up inspection. Preflight estimates tokens as ASCII characters / 3 + non-ASCII characters × 2, including the system prompt and tool definitions. The Agent context threshold is 100,000 estimated tokens, defined by `CONTEXT_TOKEN_LIMIT` in `build_workflow.py`. At or below this threshold, the workflow neither compresses history nor shows a long-context notice. Above it, the workflow tries to summarize older complete exchanges in batches of at most 10,000 estimated tokens. The batch size limits individual summary calls; it is not the Agent context threshold. Accepted summaries must fit 1,600 estimated tokens and reduce the original material. Above the same 100,000-token advisory threshold, a rejected summary receives one corrective attempt. If the current question or evidence is large, an older exchange cannot fit a summary batch, or summarization remains unsuccessful, the Agent continues with the preserved input and a visible long-context notice. Rejected summaries preserve the saved memory and history position. Actual model context capacity and transport/authentication failures can still prevent generation. Each original exchange remains exportable until its 90-day expiry. The composer and Gateway accept questions with attached FASTA up to 300,000 characters; only the turn-submission endpoint accepts request bodies up to 2 MB, so a 100,000-token ASCII question is not rejected by the old 24,000-character / 256 KB limits. Other request limits and the model output-token caps are unchanged. Regenerate and deploy the n8n workflow for a threshold change to take effect in a running Agent.
- The gateway atomically claims each prediction input within a turn. Repeated identical calls reuse the saved record or report that the original job is still running. Queue/timeout options do not bypass this check. If a predictor fails, additional calls to that predictor in the same turn return its saved failure; a new user turn is required to try it again. Different successful candidate inputs may still be compared. This is enforced by the gateway, not just by an instruction to the language model.
- Final replies, result citations and memory updates are committed in one SQLite transaction using the session memory revision. A stale version, cancellation, empty reply or invalid summary leaves the original memory intact. The memory panel shows stored coverage and compression progress; failed summaries never replace raw history.
- Streaming text is checkpointed separately in `turns.partial_output`. It remains visible after interruption but never enters completed conversation memory. The final validated answer replaces it atomically. Closing a browser stream does not cancel the independent worker; the explicit Stop action does.
- n8n execution payload persistence is disabled in this workflow's settings. The gateway automatically enforces the 90-day retention policy below. Current list endpoints show the latest 100 conversations / 200 results; additional records remain directly addressable by ID and their saved links until their expiry.

## 90-day retention

- Results and individual conversation turns expire **90 × 24 hours after `created`** (UTC epoch), including failed results and partial responses. Viewing, downloading, opening a link or continuing a conversation does not reset this timestamp. API records include `expires_at` and `retention_days`; `GET /api/workspace/retention` exposes the policy.
- Maintenance runs at gateway startup and hourly thereafter. Each transaction deletes up to 1,000 expired results/turns, their events, and old empty sessions. A pass drains up to 100 batches or 30 seconds of database work. Large backlogs continue on the next pass (`backlog_possible` in the report); downtime also delays deletion. Deletion therefore occurs on a maintenance pass after expiry, not at an exact second.
- Recent turns/results survive even if their parent is old. Surviving results are detached from deleted parents. Removing old exchanges resets the affected session summary, summarized count and token estimate, increments its memory revision, and records `retention_reset_at`; subsequent context is built from remaining exchanges. Live sessions and their attached/read results are protected while an Agent lease is valid, within the existing two-hour execution limit. Expired leases do not prevent cleanup indefinitely.
- Only recognized ESMFold job files (`<label>_<12 hex digits>`, PDB/FASTA/log/error suffixes) are pruned from `/tmp/esmfold_output`, `/tmp/esmfold_fasta` and `/tmp/static/pdb`. A surviving structure result protects its referenced job. Files must be older than 90 days by modification time. Symlink files/directories are skipped. Configure alternate **dedicated** roots with `ENZYMIND_RETENTION_ARTIFACT_ROOTS` as a JSON array of absolute paths; `[]` disables artifact pruning. No model weights or reference databases are scanned.
- Project backups in the database's sibling `backups/` directory (`.sqlite3`, `.sqlite`, `.db`, `.json`) are rotated after 90 days by backup-file modification time. This is a separate backup retention window: an online-expired record may remain in a newer backup until that backup expires. Each artifact root and the backup directory are limited to 5,000 deleted files per pass. External backup systems require their own retention configuration.
- n8n's shared database is **excluded**. This Agent workflow already disables execution payload persistence; configure shared n8n retention separately if other workflows save executions. The scientific service databases and other projects' files are also excluded.
- The Results library, model forms and Agent show the policy. Saved records show expiry dates, highlighted during their final seven days. Download the full result JSON and needed SVG/PDB files before expiry; conversation exports contain messages and result references, not a complete backup of every result. An access-key export only restores access to records still retained. Missing-result errors explain possible expiry without exposing another owner's records.

SQLite page reclamation uses [incremental auto-vacuum](https://www.sqlite.org/pragma.html#pragma_auto_vacuum) and a bounded 8,192-page reclamation plus WAL checkpoint after each pass. New databases enable this automatically. Existing databases require a one-time full `VACUUM` **while the gateway is stopped**, with enough temporary disk space. This operation preserves records but rewrites database pages; take a consistent SQLite backup first. Without this migration, deleted pages remain reusable inside the file and the maintenance report shows `incremental_vacuum: false`.

Run from the repository root with the gateway's environment/database path:

```bash
# Review one batch and eligible files; no user records or files are deleted.
gateway/venv/bin/python -m gateway.retention --dry-run
# Existing databases: stop the gateway, run this once, then restart it.
gateway/venv/bin/python -m gateway.retention --initialize-vacuum
# Optional immediate pass; the gateway also schedules this automatically.
gateway/venv/bin/python -m gateway.retention --run
```

The store constructor applies additive schema/index migrations even for `--dry-run`. Inspect the single `maintenance` row named `retention` for the last run's timestamp, counts, file errors, remaining backlog flag and storage reclamation status. The row is overwritten rather than appended indefinitely. Cleanup failures are logged and retried at the next hourly pass; busy SQLite space reclamation is deferred without undoing completed record deletion. Run one gateway worker as required by the existing workspace architecture.

## Scientific result contract

Every result has a stable UUID and URL, tool, evidence category, original input, completion state, duration, creation time and complete upstream payload. Both individual web tools and Agent tools save this envelope. Existing API response fields remain available; the web API adds `workspace_result` metadata.

The shared result renderer handles nested records, tables, BLAST alignments, kinetic values, EasIFA residue annotations, source compatibility messages and structure exploration. kcat and Km are displayed in the linear units returned by their services. A model score, predicted site score, database annotation and structure pLDDT are kept distinct.

The structure viewer uses Mol* 5.6.1 with a custom residue color theme and camera-following SVG labels with chain/style/site filters, sequence selection, residue labels, coordinate export and PNG export. A coordinate-based PDB alpha-carbon SVG preview is used if Mol* / WebGL is unavailable, with an explicit reason and retry control. It preserves chain IDs and insertion codes, breaks unresolved backbone gaps, and does not renumber residues. Chain-ambiguous or identity-mismatched site mappings are flagged. Historical EasIFA records without coordinates retain their available sequence and residue table; missing structure data are not fabricated.

## Streaming protocol

The workspace uses n8n's [native streaming response](https://docs.n8n.io/workflows/streaming/): Webhook `responseMode: streaming`, Agent `enableStreaming: true`, and Respond to Webhook version 1.5 with streaming enabled. The gateway decodes n8n's NDJSON frames, forwards only `Research Agent` text, and requires a separate `Workspace response` completion envelope before committing the answer, references and memory. An Agent `end` frame or a disconnected transport alone cannot mark a turn completed. Memory summaries and other internal node content are not streamed to the conversation.

After the normal idempotent POST starts a turn, `GET /api/workspace/turns/{id}/stream` uses the existing `X-Enzymind-Client` header and returns SSE events: `snapshot`, `delta`, `progress`, `results`, and `done`. Every connection starts with saved text and progress; reconnecting replaces the snapshot instead of replaying deltas. The browser retains the same turn ID, supports split UTF-8 input and aborts only its subscription when changing conversations. `done` carries the authoritative final or interrupted turn. No access credential is put in a stream URL.

The [streaming verification record](../../frontend/tests/verification-streaming-2026-11-09.json) covers early text delivery through the real frontend proxy, native model streaming, tool-result citations, browser disconnect/refresh/Stop, and iterative memory compression including failure preservation and recovery.

## Verification

The [2026-11-06 verification record](../../frontend/tests/verification-2026-11-06.json) is the historical pre-deployment check. The workflow was subsequently updated and activated on 2026-11-09 using the existing target `4L8PfUS3VVcclwLh` and its existing model binding. The gateway, ProtParam, alignment and structure services were restarted. The database migration preserved the 7 existing sessions, 13 turns and 19 result records; later verification runs add their own isolated workspaces. Pre-rollout database and workflow backups are stored privately in `files/workspace/backups/2026-11-09/`, outside version control. No management API key is stored in the repository.

The real compression check started with five explicitly synthetic long exchanges. It made three summary passes before the Agent request, retained all original exchanges, and correctly answered the subsequent follow-up without calling scientific tools. An oversized Unicode question failed visibly and left the previous summary and revision unchanged. Result links are normalized only against records owned by the workspace, including historical answers on display; stored raw history is not rewritten.

The [2026-11-09 deployment and verification record](../../frontend/tests/verification-2026-11-09.json) records 25 gateway tests, 7 workflow tests and 21 browser tests, plus live example and memory checks. Function, reaction, kinetics, structure/properties and saved-evidence cases completed. The P00698 EasIFA request timed out, and NCBI BLAST remained queued; partial evidence and failure records were retained. These external jobs were not treated as successful predictions.

M-CSA display identifiers such as `M-CSA-203` normalize to the service's numeric ID `203`. Example prompts require separate source tables for UniProt and PDB residue numbering and leave missing amino-acid identities unspecified. Record 203 provides residue data but no mechanism summary. Exact source tables were checked in the live follow-up; surrounding model prose still needs scientific review and is not a substitute for the saved evidence.

### Representative Agent examples

The Workspace examples use concrete inputs and provide a starting question, expected evidence, source links and a follow-up. Selection and “Load starting question” do not submit a request. Existing conversations can reopen the examples. The evidence-reuse example requires an attachment.

| Example | Input | Coverage |
| --- | --- | --- |
| From sequence to function | Porcine trypsin, P00761 | Database annotation, enzyme recognition and EC classification |
| From reaction to enzyme class | Ethyl acetate hydrolysis reaction SMILES | Returned EC recommendations and their limitations |
| Evaluate an enzyme–substrate pair | Yeast ADH1, P00330 + ethanol; follow-up with 1-propanol | Substrate score, kcat, Km and reuse of previous results |
| Connect residues to mechanism | Chicken lysozyme C, P00698; M-CSA 203 | EasIFA, annotated sites, catalytic residues and mechanism, with explicit numbering constraints |
| Build a sequence and structure profile | Full canonical P00698 precursor sequence | Sequence, physicochemical properties, ESMFold and pLDDT |
| Assess sequence-similarity evidence | P00698 | BLAST identity, query coverage, E-value and remote queue handling |
| Continue from saved evidence | A result attached from the workspace | Exact-value retrieval, failure interpretation, memory and no repeated predictions |

Protein identities were checked against [UniProt P00761](https://www.uniprot.org/uniprotkb/P00761/entry), [P00330](https://www.uniprot.org/uniprotkb/P00330/entry) and [P00698](https://www.uniprot.org/uniprotkb/P00698/entry). M-CSA availability was checked against the local curated service: P00698 resolves to record 203; P00761 did not resolve, so it was not used for the mechanism example. These are reproducible research questions, not precomputed findings or claims that the predictions agree with experiment. Tool coverage in the catalog describes the available analysis path: when an attachment already supplies the required data, the Agent can interpret it without an extra read call. EasIFA and NCBI may require a remote queue; independent retrieved records remain available when prediction/search times out.

```bash
gateway/venv/bin/python -m unittest discover -s gateway/tests -v
node frontend/tests/resultData.test.mjs
node frontend/tests/inputMapping.test.mjs
node agent_n8n/workspace/tests/workflow.test.mjs
cd frontend
npm run build
```

`frontend/tests/viewer.html` is a development-only fixture with explicitly synthetic two-chain coordinates. It tests residue identity, chain ambiguity, filters and WebGL fallback; it is not scientific evidence and is not an application route.

Manual checks: start a conversation, refresh, ask about the previous goal; run one real scientific tool; open its citation and residue table; attach a result from an individual tool and request interpretation without recomputation; inspect failure/cancellation states; test the viewer with WebGL enabled and disabled; verify the mobile conversation menu. Automated integration tests use mocked upstream services, so they do not establish scientific model accuracy or availability of every inference service.


### Browser verification

Use Node 24.14.1+ (required by Ketcher 3.18). After `npm ci` in `frontend`:

```bash
npm run build
# In separate terminals:
npm run dev -- --host 127.0.0.1 --port 3011 --strictPort
npm run preview -- --host 127.0.0.1 --port 3012 --strictPort
# Run against built application; the explicitly synthetic Mol* fixture uses dev.
ENZYMIND_TEST_URL=http://127.0.0.1:3012/enzymind/ npm run test:browser
```

`CHROME_BIN` overrides `/opt/google/chrome/chrome`. `ENZYMIND_VIEWER_TEST_URL` overrides the fixture URL. The suite uses mocked scientific responses for deterministic page checks and loads real Ketcher/Indigo and Mol* WebGL. It covers all 11 tool pages, FASTA selection, mobile layout, Home shortcuts, navigation during requests, chemical round trips, structure controls, exports, failure records and Agent memory restoration. Browser traces, screenshots and JSON reports go to `/tmp/enzymind-browser-*`.

`guidance.spec.mjs` verifies first-visit guides with empty browser storage, per-page persistence, animated expansion previews without inference requests, manual replay, keyboard/focus handling, reduced motion, mobile positioning, disabled storage and dismissible retention notices. Other browser tests use `fixtures.mjs` to represent returning users whose guides have already been seen. UI preferences are independent of the workspace access key and do not change server-side retention. The small expiry-date link and existing JSON export remain available after a result notice is dismissed.

To activate memory changes, update/restart the gateway first, then update the existing workspace workflow with `deploy.py --target ...` and its existing model binding. The added progress callback also points to the configured gateway URL. No management credential is embedded in source. Importing the JSON alone does not activate a workflow or configure a model credential.

### Citation and annotation reliability

The Agent must copy result URLs from current tool responses, attached evidence or the result index. Historical assistant prose is not a source of verified URLs. Missing source URLs remain plain text; the Agent must not invent links. The gateway repairs result destinations only when the UUID belongs to the requesting workspace and removes reserved `.invalid` destinations that cannot be resolved. The Markdown renderer also blocks those links during streaming and when displaying older answers. Assistant history and summaries are cleaned before entering context; original exchanges remain stored. New compressed summaries are cleaned before their atomic memory commit.

Enzyme annotation, catalytic reactions, protein function, annotated sites, reported kinetics and sequence information use `shared/uniprot.py`, alongside BLAST, Enzyme information and ProtParam. The shared transport validates TLS certificates and returned accessions, bounds retries/time/cache size, retries transient interruptions and never caches failures. Blocking annotation calls run outside the API event loop. An upstream outage is a failed lookup, never a negative biological annotation. Existing JSON, form, batch and legacy routes retain their response contracts.

Active-site result reads also normalize EasIFA's legacy `enzyme_sequence_info` display blocks. Only trailing `&` padding is removed; each protein receives `sequence`, `sequence_length`, and `sequence_normalization` provenance. Model summaries omit the display blocks, while Python receives padding-free blocks as well as the explicit sequence fields, so older analysis code remains compatible. This applies to historical saved results without rewriting their archived database payloads; sandbox input hashes describe the normalized data actually copied. Internal gaps, malformed blocks, conflicting sequences, and ambiguous multichain records are flagged instead of guessed or renumbered. Existing generated answers and derived Python outputs remain historical records and must be recalculated to correct earlier length errors.
## Python Analysis

Workspace v2 now includes a Python Analysis HTTP tool at `/api/workspace/tools/python`.
It uses the existing turn capability and saved-result citations, with a 3-call
Python limit inside the shared 12-tool budget. Gateway JSON fields are `code`, optional
`data`, `result_ids`, and `file_ids`; no host paths or Docker options are accepted.
The n8n tool exposes a typed `code` string and an `inputs` object containing
`data`, `result_ids`, and `file_ids`; its expression constructs the Gateway body.
The non-empty wrapper accommodates n8n's JSON parameter schema, which rejects
empty objects and arrays as standalone model arguments. Include all three
wrapper keys, using empty values when unused. Only explicitly listed result IDs
are copied. Inside Python, `results[id]` is the parsed payload itself, without an
outer `data` field. kcat/Km payloads expose `success`, `kcat`/`km`, and `unit`;
previous Python calculations are under `results[id]['result']`.
HTTP admission errors are returned to the Agent as JSON `detail`; quota,
disabled, and busy responses must stop further calls, not trigger probes.
The tool is unavailable until Gateway's `ENZYMIND_PYTHON_ENABLED` is enabled and
the dedicated Rootless Runner passes preflight. See
[deployment and acceptance](../../services/python_sandbox/README.md).

For file-producing code, always use the injected `output_dir`, for example
`fig.savefig(output_dir / 'plot.png')` and
`df.to_csv(output_dir / 'data.csv', index=False)`, replacing example names with
the requested filenames. Relative files outside this directory are scratch data
and are discarded. Confirm actual exports in the tool response's `data.files`;
filenames in `result` or stdout do not create attachments. Final Agent replies
list filenames as text and cite the saved result page, which handles authenticated
previews and downloads. Direct file links and Markdown images cannot supply the
workspace download header. A real Agent integration test and its artifacts are
recorded in the sandbox validation report above.
