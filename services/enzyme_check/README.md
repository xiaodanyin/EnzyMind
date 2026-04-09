# Enzyme Check Service - Enzyme Annotation Microservice

## Overview

The Enzyme Check Service determines whether a protein is annotated as an enzyme by querying catalytic activity information from the UniProt database.

## Port

- **Service port**: 18914

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/check/enzyme` | POST | Enzyme check (JSON) |
| `/api/check/enzyme/form` | POST | Enzyme check (form) |
| `/api/check/enzyme/batch` | POST | Batch enzyme check |
| `/check/enzyme` | POST | Legacy-compatible API |

## Installation

```bash
cd /path/to/Enzymind/services/enzyme_check
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Usage Examples

### Health check

```bash
curl http://localhost:18914/health
```

### Check a single protein

```bash
curl -X POST http://localhost:18914/api/check/enzyme \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```

Response:
```json
{
    "success": true,
    "uniprot_id": "P12345",
    "is_enzyme": true,
    "message": "The sequence with UniProt ID 'P12345' is annotated as an enzyme.",
    "ec_numbers": ["1.1.1.1"]
}
```

### Batch check

```bash
curl -X POST http://localhost:18914/api/check/enzyme/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["P12345", "P00533"]}'
```

## API Docs

- **Swagger UI**: http://localhost:18914/docs
- **ReDoc**: http://localhost:18914/redoc

## Tests

```bash
pytest tests/ -v
```

## License

MIT License
