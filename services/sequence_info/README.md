# Sequence Info Service

A microservice for protein sequence information: length, molecular weight and amino acid sequence.

## Port

- **18918**

## Features

Retrieve protein sequence information from UniProt:
- Sequence length (amino acid count)
- Molecular weight (Da)
- Amino acid sequence

## API endpoints

| Method | Endpoint | Description |
|------|------|------|
| GET | `/health` | Health check |
| POST | `/api/query/sequence-info` | Query sequence information |
| POST | `/api/query/sequence-info/form` | Query using form fields |

## Installation

```bash
cd services/sequence_info
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
source venv/bin/activate
python main.py
```

The service runs at http://localhost:18918

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## API documentation

After starting the service, visit:
- Swagger UI: http://localhost:18918/docs
- ReDoc: http://localhost:18918/redoc

## curl examples

### Health check

```bash
curl http://localhost:18918/health
```

Response:
```json
{
  "status": "healthy",
  "service": "sequence_info"
}
```

### Query sequence information

```bash
curl -X POST http://localhost:18918/api/query/sequence-info \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'
```

Response:
```json
{
  "length": 402,
  "molWeight": 44674,
  "value": "MSPFFFFFAGLLLPVPVQALPIGNDPLLQGGLFSDSSSNSG..."
}
```

### Query using form fields

```bash
curl -X POST "http://localhost:18918/api/query/sequence-info/form?uniprot_id=P12345"
```

## Response fields

| Field | Type | Description |
|------|------|------|
| length | int/null | Sequence length (amino acid count) |
| molWeight | int/null | Reported mass, or calculated average mass of the returned unmodified sequence, in Da |
| molWeight_source | string/null | Reported or calculated mass provenance |
| molWeight_note | string/null | Explanation when a usable mass cannot be returned |
| value | string/null | Amino acid sequence |
| source | object/null | UniProt record provenance |

## Data sources

The [shared UniProt client](../../shared/README-uniprot.md) checks the configured local snapshot and exact-accession sequence index before the official API. Sequence Information and Enzyme Information use the same mass calculation helper: preserve reported mass when available, otherwise calculate it from a complete unambiguous sequence and label its source. An unavailable mass includes a reason in `molWeight_note`.
