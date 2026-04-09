# Function Get Service - Protein Function Query Microservice

## Overview

Function Get Service is a microservice for querying protein function information, retrieving protein function descriptions, names, source organisms, and gene names from the UniProt database.

## Port

- **Service Port**: 18911

## Features

- Single protein function query
- Batch protein function query
- Batch query by file upload
- Support for both JSON and Form input formats
- Automatic deduplication
- Comprehensive error handling

## API Endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/health` | GET | Health check |
| `/api/query/function` | POST | Function query in JSON format |
| `/api/query/function/form` | POST | Function query in Form format |
| `/api/query/function/batch` | POST | Batch function query |
| `/api/query/function/file` | POST | Batch query by file upload |
| `/query/function` | POST | Compatible with legacy API |

## Installation

### 1. Create Virtual Environment

```bash
cd /path/to/Enzymind/services/function_get
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Service

```bash
python main.py
```

The service will start at http://localhost:18911.

## Usage Examples

### Health Check

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

### Query Protein Function (JSON Format)

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

### Query Protein Function (Form Format)

```bash
curl -X POST http://localhost:18911/api/query/function/form \
  -d "query=P12345"
```

### Batch Query

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

### File Upload Query

Prepare a text file `ids.txt` with one UniProt ID per line:

```text
# This is a comment line, will be ignored
P12345
Q9Y6K9
P00533
```

```bash
curl -X POST http://localhost:18911/api/query/function/file \
  -F "file=@ids.txt"
```

## API Documentation

After starting the service, you can access the interactive API documentation at the following addresses:

- **Swagger UI**: http://localhost:18911/docs
- **ReDoc**: http://localhost:18911/redoc

## Return Field Description

| Field | Type | Description |
|------|------|------|
| `success` | boolean | Whether the query was successful |
| `uniprot_id` | string | UniProt accession number |
| `function` | string/null | Protein function description |
| `protein_name` | string/null | Protein name |
| `organism` | string/null | Source organism |
| `gene_names` | array/null | List of gene names |
| `error` | string/null | Error message (if failed) |

## Testing

Run unit tests:

```bash
source venv/bin/activate
pytest tests/ -v
```

## Error Handling

The service handles the following error cases:

- **400 Bad Request**: Invalid input parameters
- **UniProt ID does not exist**: Returns success=false with explanation
- **Network timeout**: Returns success=false with timeout message
- **Connection error**: Returns success=false with connection error message

## Data Source

All protein function information is sourced from the [UniProt](https://www.uniprot.org/) database.

## License

MIT License
