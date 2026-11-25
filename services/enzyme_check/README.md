# Enzyme Check Service

## Overview

This service checks whether a protein is annotated as an enzyme using catalytic-activity and EC annotations from UniProt.

## Port

- **Service port**: 18914

## API endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/health` | GET | Health check |
| `/api/check/enzyme` | POST | Enzyme annotation check (JSON) |
| `/api/check/enzyme/form` | POST | Enzyme annotation check (form) |
| `/api/check/enzyme/batch` | POST | Batch checks |
| `/check/enzyme` | POST | Legacy API compatibility |

## Installation

```bash
cd /path/to/EnzyMind/services/enzyme_check
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Examples

### Health check

```bash
curl http://localhost:18914/health
```

### Check one protein

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

### Batch checks

```bash
curl -X POST http://localhost:18914/api/check/enzyme/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["P12345", "P00533"]}'
```

## API documentation

- **Swagger UI**: http://localhost:18914/docs
- **ReDoc**: http://localhost:18914/redoc

## Tests

```bash
pytest tests/ -v
```

## License

MIT License
