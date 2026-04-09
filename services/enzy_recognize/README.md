# Enzyme Recognition Service

## Overview

This service determines whether a given protein sequence is an enzyme. It uses the ESM2 protein language model to extract sequence features and a trained MLP classifier for prediction.

## Features

- Supported input formats:
  - Amino acid sequence string
  - UniProt ID (sequence fetched automatically from UniProt)
  - FASTA file upload
  - FASTA-formatted content

## API Endpoints

### POST /api/recognize/enzyme

Enzyme recognition prediction.

**Parameters:**
- `input_type` (required): one of `fasta`, `sequence`, `uniprot`
- `query` (optional): amino acid sequence or UniProt ID
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

Health check.

### GET /

Service info.

## Installation

```bash
cd services/enzy_recognize
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```


## Run

```bash
python main.py
# or
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

# Recognize a sequence
result = client.recognize_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")
print(f"Is enzyme: {result['result']['is_enzyme']}")
print(f"Confidence: {result['result']['confidence']}")

# Using UniProt ID
result = client.recognize_uniprot("P12345")

# Upload FASTA file
result = client.recognize_fasta("/path/to/sequence.fasta")
```

### curl

```bash
# Recognize a sequence
curl -X POST "http://localhost:8080/api/recognize/enzyme" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "sequence", "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'

# Using UniProt ID
curl -X POST "http://localhost:8080/api/recognize/enzyme" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "uniprot", "query": "P12345"}'
```

## Directory Structure

```
enzy_recognize/
├── main.py              # FastAPI app entry
├── client.py            # API client
├── requirements.txt     # dependencies
├── README.md            # documentation
├── models/
│   ├── __init__.py
│   └── enzyme_predictor.py  # enzyme predictor model
└── tests/
    ├── __init__.py
    └── test_api.py      # test cases
```

## Port

Default port: 18901
