# Active Sites Prediction Service

## Overview

This service predicts enzyme active sites using the EasIFA (Easy Identification of Functional Active sites) API. It supports multiple input types and both synchronous and asynchronous workflows.

## Features

- Multiple input types:
    - UniProt ID via `/from_uniprot`
    - Amino acid sequence via `/from_sequence`
    - PDB structure file via `/from_structure`
- Synchronous and asynchronous prediction modes
    - Sync: submit and wait for the result
    - Async: submit, get a `job_id`, then poll for status/results
- Automatic input-type detection

## API Endpoints

### Async submission

#### POST /api/predict/active-sites/submit/uniprot
Submit an async job with a UniProt ID.

**Request body**
```json
{
    "uniprot_id": "P12345",
    "use_celery": true
}
```

**Response**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "uniprot"
}
```

#### POST /api/predict/active-sites/submit/sequence
Submit an async job with an amino acid sequence (JSON input).

**Request body**
```json
{
    "aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ...",
    "rxn_smiles": "CC(=O)O>>CC(=O)OC",
    "use_celery": true
}
```

**Response**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "sequence"
}
```

#### POST /api/predict/active-sites/submit/sequence/form
Submit an async job with an amino acid sequence (form input).

**Parameters**
- `aa_sequence` (required): amino acid sequence
- `rxn_smiles` (optional): reaction SMILES
- `use_celery` (optional): whether to use Celery async processing, default true

#### POST /api/predict/active-sites/submit/structure
Submit an async job with a PDB structure file.

**Parameters**
- `pdb_file` (required): PDB file
- `rxn_smiles` (optional): reaction SMILES
- `use_celery` (optional): whether to use Celery async processing, default true

**Response**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "structure"
}
```

### Job status and results

#### GET /api/predict/active-sites/job/{job_id}
Check job status.

**Response**
```json
{
    "success": true,
    "status": "completed",
    "data": {}
}
```

#### GET /api/predict/active-sites/results/{job_id}
Fetch job results.

**Response**
```json
{
    "success": true,
    "data": {},
    "markdown": "| Residue Index | Residue Name | Active Type | Confidence |..."
}
```

### Synchronous prediction

#### POST /api/predict/active-sites
Sync prediction by UniProt ID (submit and wait).

**Request body**
```json
{
    "uniprot_id": "P12345",
    "use_celery": true
}
```

**Response**
```json
{
    "result": "| Residue Index | Residue Name | Active Type | Confidence |\n|---|---|---|---|\n| 145 | HIS | catalytic | 0.95 |"
}
```

#### POST /api/predict/active-sites/sequence
Sync prediction by amino acid sequence (form input).

**Parameters**
- `aa_sequence` (required): amino acid sequence
- `rxn_smiles` (optional): reaction SMILES
- `use_celery` (optional): whether to use Celery, default true
- `timeout` (optional): seconds, default 600

#### POST /api/predict/active-sites/structure
Sync prediction by PDB structure file.

**Parameters**
- `pdb_file` (required): PDB file
- `rxn_smiles` (optional): reaction SMILES
- `use_celery` (optional): whether to use Celery, default true
- `timeout` (optional): seconds, default 600

### Auto-detect endpoint

#### POST /api/predict/active-sites/auto
Auto-detect input type and submit. Supports UniProt ID or amino acid sequence; for PDB files use `/submit/structure`.

**Parameters**
- `input_data` (required): UniProt ID or amino acid sequence
- `rxn_smiles` (optional): reaction SMILES (for sequence input)
- `use_celery` (optional): whether to use Celery, default true

**Response**
```json
{
    "success": true,
    "job_id": "abc123",
    "task_manager": "celery",
    "input_type": "uniprot"
}
```

### GET /health
Health check.

## Installation

```bash
cd services/active_sites
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Run

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 18907 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### curl

```bash
# ===== UniProt ID input =====
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

# Synchronous prediction (may take time)
result = client.predict_active_sites("P12345")
print(result)

# Async submission
submit_result = client.submit_task("P12345")
if submit_result.get("success"):
        job_id = submit_result.get("job_id")
        print(f"Job submitted: {job_id}")

        # Wait for result
        result = client.submit_and_wait("P12345", poll_interval=5, max_wait_time=600)
        print(result)
```

## Directory Structure

```
active_sites/
├── main.py              # FastAPI app entry
├── client.py            # API client
├── conftest.py          # pytest config
├── requirements.txt     # dependencies
├── README.md            # documentation
├── models/
│   ├── __init__.py
│   ├── active_sites_predictor.py  # active site predictor
│   └── utils.py         # utilities
└── tests/
        ├── __init__.py
        └── test_api.py      # test cases
```

## Port

Default port: 18907

## External Dependencies

- EasIFA API endpoints:
    - `/from_uniprot` - UniProt ID input
    - `/from_sequence` - amino acid sequence input
    - `/from_structure` - PDB file input
- pandas for data processing and Markdown table generation
- tabulate for table formatting

## Model Notes

Active site prediction is based on EasIFA:

1. **Input types**
     - UniProt ID: fetches protein info from UniProt
     - Amino acid sequence: optional reaction SMILES can aid prediction
     - PDB structure file: optional reaction SMILES can aid prediction

2. **Output**
     - Residue Index: residue position
     - Residue Name: residue name
     - Active Type: type (e.g., catalytic, binding)
     - Confidence: confidence score

## Async Mode

Because prediction can take minutes, use async mode when needed:

1. Submit via `/submit/*`
2. Receive `job_id`
3. Poll `/api/predict/active-sites/job/{job_id}` for status
4. When `completed`, fetch results via `/api/predict/active-sites/results/{job_id}`

## Input Type Reference

| Input type | Submit endpoint | Sync endpoint | Reaction SMILES required? |
|------------|-----------------|---------------|---------------------------|
| UniProt ID | `/submit/uniprot` | `/api/predict/active-sites` | No |
| Amino acid sequence | `/submit/sequence` | `/sequence` | Optional |
| PDB structure file | `/submit/structure` | `/structure` | Optional |
| Auto-detect | `/auto` | - | Optional (for sequences) |

## Legacy Endpoint

For backward compatibility:

- `POST /api/query/active-sites` — alias of `/api/predict/active-sites`
