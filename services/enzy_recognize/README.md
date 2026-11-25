# Enzyme Recognition Service

## Overview

This service predicts whether a protein is an enzyme. It extracts sequence features with ESM-2 and applies a trained MLP classifier.

## Features

- Supported input formats:
  - Amino acid sequence string
  - UniProt accession (resolved through the shared UniProt client)
  - FASTA file upload
  - FASTA content

## API endpoints

### POST /api/recognize/enzyme

Enzyme recognition endpoint.

**Parameters:**
- `input_type` (required): Input type: `fasta`, `sequence`, or `uniprot`
- `query` (optional): Query string (amino acid sequence or UniProt accession)
- `file` (optional): FASTA file upload

**Response:**
```json
{
    "result": {
        "is_enzyme": true,
        "confidence": 0.9876
    }
}
```

### GET /health

Health check endpoint.

### GET /

Service information endpoint.

## Installation

```bash
cd services/enzy_recognize
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```


## Running

```bash
python main.py
# Or
uvicorn main:app --host 0.0.0.0 --port 18901 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### Python client

```python
from client import EnzymeRecognitionClient

client = EnzymeRecognitionClient(base_url="http://localhost:18901")

# Classify a sequence
result = client.recognize_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")
print(f"Is enzyme: {result['result']['is_enzyme']}")
print(f"Confidence: {result['result']['confidence']}")

# Use a UniProt accession
result = client.recognize_uniprot("P12345")

# Upload a FASTA file
result = client.recognize_fasta("/path/to/sequence.fasta")
```

### curl

```bash
# Classify a sequence
curl -X POST "http://localhost:8080/api/recognize/enzyme" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "sequence", "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'

# Use a UniProt accession
curl -X POST "http://localhost:8080/api/recognize/enzyme" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "uniprot", "query": "P12345"}'
```

## Directory layout

```
enzy_recognize/
├── main.py              # FastAPI application
├── client.py            # API client
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   └── enzyme_predictor.py  # Enzyme recognition model
└── tests/
    ├── __init__.py
    └── test_api.py      # Tests
```

## Port

Default port: 18901
