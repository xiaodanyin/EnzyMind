# Sequence Info Service

Microservice for querying protein sequence information (sequence length, molecular weight, amino acid sequence).

## Port

- **18918**

## Features

Query protein sequence information from UniProt:
- Sequence length (number of amino acids)
- Molecular weight (Daltons)
- Amino acid sequence

## API Endpoints

| Method | Endpoint | Description |
|------|------|------|
| GET | `/health` | Health check |
| POST | `/api/query/sequence-info` | Query sequence information |
| POST | `/api/query/sequence-info/form` | Form-based query |

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

The service will start at http://localhost:18918

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

## API Documentation

After starting the service, visit:
- Swagger UI: http://localhost:18918/docs
- ReDoc: http://localhost:18918/redoc

## curl Examples

### Health Check

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

### Query Sequence Information

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

### Form-based Query

```bash
curl -X POST "http://localhost:18918/api/query/sequence-info/form?uniprot_id=P12345"
```

## Response Fields

| Field | Type | Description |
|------|------|------|
| length | int | Sequence length (number of amino acids) |
| molWeight | int | Molecular weight (Daltons) |
| value | string | Amino acid sequence |

## Data Source

- UniProt REST API: https://rest.uniprot.org/uniprotkb/{id}.json
