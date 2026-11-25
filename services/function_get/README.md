# Protein Function Query Service

## Overview

This service retrieves protein function descriptions, names, organisms and gene names from UniProt.

## Port

- **Service port**: 18911

## Features

- Single-protein function queries
- Batch protein function queries
- Batch queries from an uploaded file
- JSON and form inputs
- Automatic deduplication
- Error handling

## API endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/health` | GET | Health check |
| `/api/query/function` | POST | Function query (JSON) |
| `/api/query/function/form` | POST | Function query (form) |
| `/api/query/function/batch` | POST | Batch function queries |
| `/api/query/function/file` | POST | Batch queries from an uploaded file |
| `/query/function` | POST | Legacy API compatibility |

## Installation

### 1. Create a virtual environment

```bash
cd /path/to/EnzyMind/services/function_get
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the service

```bash
python main.py
```

The service runs at http://localhost:18911.

## Examples

### Health check

```bash
curl http://localhost:18911/health
```

Response:
```json
{
    "status": "healthy",
    "service": "function_get",
    "version": "1.0.0"
}
```

### Query protein function (JSON)

```bash
curl -X POST http://localhost:18911/api/query/function \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```

Response:
```json
{
    "success": true,
    "uniprot_id": "P12345",
    "function": "Catalyzes the irreversible transamination of the L-tryptophan metabolite L-kynurenine...",
    "protein_name": "Aspartate aminotransferase, mitochondrial",
    "organism": "Homo sapiens",
    "gene_names": ["GOT2", "FABP-1"],
    "error": null
}
```

### Query protein function (form)

```bash
curl -X POST http://localhost:18911/api/query/function/form \
  -d "query=P12345"
```

### Batch queries

```bash
curl -X POST http://localhost:18911/api/query/function/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["P12345", "Q9Y6K9", "P00533"]}'
```

Response:
```json
{
    "results": {
        "P12345": {
            "success": true,
            "uniprot_id": "P12345",
            "function": "...",
            "protein_name": "...",
            "organism": "Homo sapiens",
            "gene_names": ["GOT2"],
            "error": null
        },
        "Q9Y6K9": {
            "success": true,
            "uniprot_id": "Q9Y6K9",
            "function": "...",
            "protein_name": "...",
            "organism": "Homo sapiens",
            "gene_names": ["..."],
            "error": null
        }
    },
    "total": 3,
    "successful": 3
}
```

### Query using an uploaded file

Prepare an `ids.txt` file with one UniProt accession per line:

```text
# This comment line is ignored
P12345
Q9Y6K9
P00533
```

```bash
curl -X POST http://localhost:18911/api/query/function/file \
  -F "file=@ids.txt"
```

## API documentation

After starting the service, open the interactive API documentation:

- **Swagger UI**: http://localhost:18911/docs
- **ReDoc**: http://localhost:18911/redoc

## Response fields

| Field | Type | Description |
|------|------|------|
| `success` | boolean | Whether the query succeeded |
| `uniprot_id` | string | UniProt accession |
| `function` | string/null | Protein function description |
| `protein_name` | string/null | Protein name |
| `organism` | string/null | Organism |
| `gene_names` | array/null | Gene names |
| `error` | string/null | Error message on failure |

## Tests

Run unit tests:

```bash
source venv/bin/activate
pytest tests/ -v
```

## Error handling

The service handles these error cases:

- **400 Bad Request**: Invalid input parameters
- **UniProt accession not found:** returns success=false with an explanation
- **Network timeout:** returns success=false with timeout details
- **Connection error:** returns success=false with connection failure details

## Data sources

Protein function annotations come from [UniProt](https://www.uniprot.org/), using the shared local-first resolver.

## License

MIT License
