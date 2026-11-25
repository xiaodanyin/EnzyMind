# Catalytic Activity Query Service

## Overview

This service retrieves catalytic-activity annotations from UniProt, including EC numbers, Rhea identifiers and reaction descriptions.

## Port

- **Service port**: 18913

## Features

- Query protein catalytic activity
- Retrieve EC numbers and Rhea identifiers
- Batch query support
- Batch queries from an uploaded file
- Markdown output

## API endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/health` | GET | Health check |
| `/api/query/catalytic-activity` | POST | Catalytic-activity query (JSON) |
| `/api/query/catalytic-activity/form` | POST | Query using form fields |
| `/api/query/catalytic-activity/batch` | POST | Batch queries |
| `/api/query/catalytic-activity/file` | POST | Batch queries from an uploaded file |
| `/query/catalytic_activity` | POST | Legacy API compatibility |

## Installation

### 1. Create a virtual environment

```bash
cd /path/to/EnzyMind/services/ec_reaction_info
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

The service runs at http://localhost:18913.

## Examples

### Health check

```bash
curl http://localhost:18913/health
```

### Query catalytic activity

```bash
curl -X POST http://localhost:18913/api/query/catalytic-activity \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```

Response:
```json
{
    "success": true,
    "uniprot_id": "P12345",
    "activities": [
        {
            "reaction_name": "ATP + L-aspartate + L-glutamine = ...",
            "ec_number": "6.3.5.4",
            "rhea_id": "11844",
            "evidence": ["ECO:0000269"]
        }
    ],
    "count": 1,
    "markdown": "### Catalytic Activities for `P12345`..."
}
```

### Batch queries

```bash
curl -X POST http://localhost:18913/api/query/catalytic-activity/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["P12345", "Q9Y6K9"]}'
```

### File upload

```bash
curl -X POST http://localhost:18913/api/query/catalytic-activity/file \
  -F "file=@ids.txt"
```

## API documentation

- **Swagger UI**: http://localhost:18913/docs
- **ReDoc**: http://localhost:18913/redoc

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Data sources

Catalytic-activity annotations come from [UniProt](https://www.uniprot.org/), using the shared local-first resolver.

## License

MIT License

## EC-number compatibility endpoint

`POST /api/query/ec-info` accepts `{"query":"3.2.1.17"}` (also `ec_number`),
returning the accepted name, hierarchy, catalytic activity, entry status and
source metadata. Partial classes such as `3.2.-.-` have no invented enzyme name
or reaction. Transferred and deleted entries are explicitly marked. Unknown
codes return `success: false` with `code: ec_not_in_reference`; malformed inputs
return HTTP 422. A UniProt accession (`query` or `uniprot_id`) uses the existing
catalytic-activity query.

The service snapshot and frontend labels come from the same official ENZYME
release, with source SHA-256 hashes and SIB CC BY 4.0 attribution. To update both
from an unmodified matching pair of `enzyme.dat` and `enzclass.txt`, run from the
repository root:

```bash
python3 scripts/build_ec_reference.py /path/to/enzyme-source
python3 scripts/build_ec_reference.py /path/to/enzyme-source --include-activities --output services/ec_reaction_info/data/ec-reference.json
```
