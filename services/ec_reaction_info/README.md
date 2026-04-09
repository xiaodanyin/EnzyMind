# EC Reaction Info Service - Catalytic Activity Microservice

## Overview

The EC Reaction Info Service queries protein catalytic activity information, retrieving EC numbers, Rhea IDs, and reaction descriptions from the UniProt database.

## Port

- **Service port**: 18913

## Features

- Query protein catalytic activity
- Retrieve EC numbers and Rhea IDs
- Batch queries
- File upload for batch queries
- Markdown output

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/query/catalytic-activity` | POST | Catalytic activity query (JSON) |
| `/api/query/catalytic-activity/form` | POST | Catalytic activity query (form) |
| `/api/query/catalytic-activity/batch` | POST | Batch query |
| `/api/query/catalytic-activity/file` | POST | File upload batch query |
| `/query/catalytic_activity` | POST | Legacy-compatible API |

## Installation

### 1. Create a virtual environment

```bash
cd /path/to/Enzymind/services/ec_reaction_info
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

The service will start at http://localhost:18913.

## Usage Examples

### Health check

```bash
curl http://localhost:18913/health
```

### Catalytic activity query

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

### Batch query

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

## API Docs

- **Swagger UI**: http://localhost:18913/docs
- **ReDoc**: http://localhost:18913/redoc

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Data Source

All catalytic activity information comes from the [UniProt](https://www.uniprot.org/) database.

## License

MIT License
