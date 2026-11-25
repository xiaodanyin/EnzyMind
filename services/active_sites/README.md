# Active Site Prediction Service

## Overview

This service uses the EasIFA (Easy Identification of Functional Active sites) API to predict functional residues from UniProt accessions, protein sequences or structures.

## Features

- Supported input formats:
  - UniProt accession: `/from_uniprot`
  - Amino acid sequence: `/from_sequence`
  - PDB structure file: `/from_structure`
- Synchronous and asynchronous prediction modes:
  - Synchronous: submit a job and wait for its result
  - Asynchronous: obtain a job_id, then poll its status and retrieve the result
- Automatic input-type detection

## API endpoints

### Asynchronous submission endpoints

#### POST /api/predict/active-sites/submit/uniprot

Submit an asynchronous prediction from a UniProt accession.

**Request body:**
```json
{
    "uniprot_id": "P12345",
    "use_celery": true
}
```

**Response:**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "uniprot"
}
```

#### POST /api/predict/active-sites/submit/sequence

Submit an asynchronous prediction from an amino acid sequence (JSON).

**Request body:**
```json
{
    "aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ...",
    "rxn_smiles": "CC(=O)O>>CC(=O)OC",
    "use_celery": true
}
```

**Response:**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "sequence"
}
```

#### POST /api/predict/active-sites/submit/sequence/form

Submit an asynchronous prediction from an amino acid sequence (form).

**Parameters:**
- `aa_sequence` (required): Amino acid sequence
- `rxn_smiles` (optional): Reaction SMILES
- `use_celery` (optional): Use Celery for asynchronous processing; default true

#### POST /api/predict/active-sites/submit/structure

Submit an asynchronous prediction from a PDB structure file.

**Parameters:**
- `pdb_file` (required): PDB structure file
- `rxn_smiles` (optional): Reaction SMILES
- `use_celery` (optional): Use Celery for asynchronous processing; default true

**Response:**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "structure"
}
```

### Job status and result endpoints

Submission, status polling and result retrieval must use the same cookie or `X-Easifa-Session`. Existing URLs, parameters and response shapes remain compatible; failed private-result retrieval returns `success=false`. See the privacy compatibility section below.

#### GET /api/predict/active-sites/job/{job_id}

Check job status.

**Response excerpt (data omitted):**
```json
{
    "success": true,
    "status": "completed",
    "data": {}
}
```

#### GET /api/predict/active-sites/results/{job_id}

Retrieve a job result.

**Response excerpt (data omitted):**
```json
{
    "success": true,
    "data": {},
    "markdown": "| Residue Index | Residue Name | Active Type | Confidence |..."
}
```

### Synchronous prediction endpoints

#### POST /api/predict/active-sites

Submit a UniProt accession and wait for the prediction result.

**Request body:**
```json
{
    "uniprot_id": "P12345",
    "use_celery": true
}
```

**Response:**
```json
{
    "result": "| Residue Index | Residue Name | Active Type | Confidence |\n|---|---|---|---|\n| 145 | HIS | catalytic | 0.95 |"
}
```

#### POST /api/predict/active-sites/sequence

Predict from an amino acid sequence synchronously (form).

**Parameters:**
- `aa_sequence` (required): Amino acid sequence
- `rxn_smiles` (optional): Reaction SMILES
- `use_celery` (optional): Use Celery; default true
- `timeout` (optional): Timeout in seconds; default 600

#### POST /api/predict/active-sites/structure

Predict from a PDB structure file synchronously.

**Parameters:**
- `pdb_file` (required): PDB structure file
- `rxn_smiles` (optional): Reaction SMILES
- `use_celery` (optional): Use Celery; default true
- `timeout` (optional): Timeout in seconds; default 600

### Automatic input detection

#### POST /api/predict/active-sites/auto

Detect the input type and submit a prediction. Accepts a UniProt accession or amino acid sequence; use `/submit/structure` for PDB files.

**Parameters:**
- `input_data` (required): UniProt accession or amino acid sequence
- `rxn_smiles` (optional): Reaction SMILES for sequence input
- `use_celery` (optional): Use Celery; default true

**Response:**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "uniprot"
}
```

### GET /health

Health check endpoint.

## Installation

```bash
cd services/active_sites
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
python main.py
# Or
uvicorn main:app --host 0.0.0.0 --port 18907 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### curl

```bash
# ===== UniProt accession input =====


curl -X POST "http://localhost:18907/api/predict/active-sites" \
    -H "Content-Type: application/json" \
    -d '{"uniprot_id": "P12345"}'

# ===== Sequence input =====
curl -X POST "http://localhost:18907/api/predict/active-sites" \
    -H "Content-Type: application/json" \
    -d '{"aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'

curl -X POST "http://localhost:18907/api/predict/active-sites" \
    -H "Content-Type: application/json" \
    -d '{"aa_sequence": "MASKLLRAVILGPPGSGKGTVCQRIAQNFGLQHLSSGHFLRENIKASTEVGEVAKQYIEKSLLVPDHVITRLMMSELENRRGQHWLLDGFPRTLGQAEALDKICEVDLVISLNIPFETLKDRLSRRWIHPPSGRVYNLDFNPPHVHGIDDVTGEPLVQQEDDKPEAVAARLRQYKDAAKPVIELYKSRGVLHQFSGTETNKIWPYVYTLFSNKITPIQSKEAY", "rxn_smiles": "CC(=O)O>>CC(=O)OC"}'
```

### Python client

```python
from client import ActiveSitesClient

client = ActiveSitesClient(base_url="http://localhost:18907")

# Health check
print(client.health_check())

# Synchronous prediction may take several minutes
result = client.predict_active_sites("P12345")
print(result)

# Submit an asynchronous job
submit_result = client.submit_task("P12345")
if submit_result.get("success"):
    job_id = submit_result.get("job_id")
    print(f"Job submitted: {job_id}")
    
    # Wait for the result
    result = client.submit_and_wait("P12345", poll_interval=5, max_wait_time=600)
    print(result)
```

## Directory layout

```
active_sites/
├── main.py              # FastAPI application
├── client.py            # API client
├── conftest.py          # pytest configuration
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   ├── active_sites_predictor.py  # Functional-site predictor
│   └── utils.py         # Utility functions
└── tests/
    ├── __init__.py
    └── test_api.py      # Tests
```

## Port

Default port: 18907

## External resources

- EasIFA API:
  - `/from_uniprot`: UniProt accession input
  - `/from_sequence`: Amino acid sequence input
  - `/from_structure`: PDB structure input
- pandas for data processing and Markdown tables
- tabulate for table formatting

## Model overview

Predictions use EasIFA (Easy Identification of Functional Active sites):

1. **Inputs:**
   - UniProt accession: retrieve protein information through the upstream database pathway
   - Amino acid sequence: optionally provide reaction SMILES
   - PDB structure: optionally provide reaction SMILES

2. **Outputs:** predicted functional residues, with fields such as:
   - Residue Index: residue position
   - Residue Name: amino acid name
   - Active Type: site class, such as catalytic or binding
   - Confidence: reported site prediction score; distinct from structure pLDDT

## Asynchronous workflow

Prediction can take several minutes. To use asynchronous processing:

1. Submit through the appropriate `/submit/*` endpoint.
2. Save the returned `job_id`.
3. Poll `/api/predict/active-sites/job/{job_id}`.
4. Once the status is `completed`, retrieve `/api/predict/active-sites/results/{job_id}`.

## Input comparison

| Input | Submission endpoint | Synchronous endpoint | Reaction SMILES |
|----------|----------|----------|-------------------|
| UniProt accession | `/submit/uniprot` | `/api/predict/active-sites` | Not required |
| Amino acid sequence | `/submit/sequence` | `/sequence` | Optional |
| PDB structure file | `/submit/structure` | `/structure` | Optional |
| Automatic detection | `/auto` | - | Optional for sequence inputs |

## Legacy endpoints

These endpoints remain available for backward compatibility:

- `POST /api/query/active-sites`: equivalent to `/api/predict/active-sites`

## EasIFA 016 privacy compatibility

Jobs are submitted as Private under the updated EasIFA policy. API URLs, JSON/form parameters, synchronous Markdown and asynchronous success/data response shapes remain compatible. This requires no database change and does not convert jobs to Public. Standard UniProt data may enter EasIFA's public Database through its existing mechanism; job permissions are independent. Sequence and PDB uploads are never made public merely to allow result retrieval.

### Identity propagation and recovery

- HTTP requests prefer `X-Easifa-Session`, otherwise the HttpOnly cookie `enzymind_easifa_session`. Without a valid identity, the service generates a separate random access key. Submission, internal polling and retrieval use the same key. HTTP users never fall back to a shared identity even if the process has a fixed Python-client key configured.
- The Gateway preserves identity headers, cookies and session cookies in responses. Active-site subroutes forward the original HTTP method and upload content, including GET and multipart requests. Proxy behavior for other services is unchanged.
- Same-origin browser requests retain their cookie. Cross-origin requests must explicitly provide `X-Easifa-Session`, preventing permissive legacy CORS settings from exposing cookie-owned jobs or recovery keys. Reverse proxies must preserve `Sec-Fetch-Site`.
- Existing synchronous web, n8n and EnzyMind MCP tools need no additional parameters; each call submits, polls and formats the result. Separate calls that should share an identity must retain the cookie or access key.
- Asynchronous scripts should use `requests.Session()`, a curl cookie jar, or the same `X-Easifa-Session` on every call. Request bodies are unchanged. A private job cannot be retrieved with its job ID alone after a stateless submission.
- `GET /api/predict/active-sites/session` explicitly returns the current `session_token` for private storage and recovery after cookie loss. Supplying the original key also reissues the cookie. Treat it as an owner credential: exclude it from logs, ordinary results and shared links. All active-site responses disable caching.
- `ActiveSitesClient` and direct `ActiveSitesPredictor` calls persist identity automatically. Specify `session_file="/private/path/easifa-session.json"` or `session_key=original_key` as needed; existing constructor parameters and methods remain supported. The default is `$XDG_STATE_HOME/enzymind/easifa/<profile>/session.json`, with state directory `~/.local/state` and a service-address-derived profile. An explicit stable file path preserves identity across address changes.
- Recovery files use EasIFA's `easifa-access` format and POSIX permissions 0600. Atomic creation prevents concurrent processes from overwriting an identity. Corrupt or unreadable files fail explicitly instead of silently generating a new key. Use separate files for different users; do not expose every user's results through a fixed service-wide identity.
- Historical Legacy Public EasIFA jobs remain accessible by their original job ID. New Private jobs require their original key or cookie; generating a key does not transfer ownership.

EnzyMind result cards do not automatically create EasIFA sharing links. To open a private result on EasIFA, restore access with the same key or recovery file. Sharing remains an explicit owner action in EasIFA.

### Configuration and rollout

The root `.env.example` lists the settings but is not loaded automatically. Supply them in the process environment or in `.env.production`, which the existing startup scripts load:

```bash
# Pin production to the upgraded HTTPS EasIFA API for this deployment.
export ENZYMIND_EASIFA_API_BASE=https://cadd.drugflow.com/easifa/api
# Only for local HTTP development; production HTTPS defaults to true.
# export ENZYMIND_EASIFA_COOKIE_SECURE=false

# Direct Python clients: use a stable private file for each user.
# export ENZYMIND_EASIFA_SESSION_FILE=/absolute/private/path/easifa-session.json
# Alternatively, set ENZYMIND_EASIFA_SESSION_KEY in the process environment.
```

Address precedence is explicit `ActiveSitesPredictor(api_base=...)`, then `ENZYMIND_EASIFA_API_BASE`, then the compatibility alias `EASIFA_API_BASE`, then fallback URLs. Empty variables count as unset. HTTP services and direct Python calls use the same rule. Fallback URLs use HTTPS and must refer to the same trusted EasIFA deployment; the API base must include `/easifa/api`.

When upgrading a fallback URL to HTTPS, a missing new identity file falls back to the corresponding existing pre-upgrade credential file, without copying or overwriting it. A corrupt existing file remains an error, rather than causing an identity change.

For a backend privacy update, deploy and restart only `active_sites` and the Gateway after active synchronous predictions finish. No database rebuild, new dependency installation, frontend build or other model restart is required for that change. Preserve recovery files and cookies.

Rollback applies to the Python code and documentation, not stored data. Preserve identity files; older code may again fail to retrieve Private results. Do not bypass EasIFA authorization or publish jobs to make rollback work.

### Validation

```bash
# From the EnzyMind root, use the existing active_sites environment.
services/active_sites/venv/bin/python -m pytest services/active_sites/tests -q
```

Tests cover all three inputs, JSON/form/multipart, synchronous tools, cookie/header identity, two-user isolation, recovery and restart, fallback URLs, Legacy Public jobs, concurrent requests, atomic identity-file creation and Gateway GET/upload forwarding. The recorded local integration used temporary service processes pinned to a local EasIFA test API, without calling production EasIFA or other EnzyMind models.

Recorded validation on 2026-11-03: 71 service/Gateway regression tests and 10 live local integration checks passed. Four new test jobs covered the original synchronous call, UniProt JSON, sequence form input, PDB multipart, restart recovery, historical Public jobs and cross-user rejection. Temporary processes were stopped; existing EnzyMind/EasIFA processes were not restarted, and no external LLM or actual n8n webhook was called.

That privacy update changed `main.py`, `models/active_sites_predictor.py`, `models/easifa_access.py`, `client.py`, `conftest.py`, `tests/test_privacy.py`, and the root Gateway/configuration documentation. The redacted local integration log was saved at `.logs/easifa-privacy-verification.log`. Recovery credentials remained in the test runtime's private directory and were excluded from the log.
