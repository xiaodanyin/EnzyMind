# EC Number Prediction Service

## Overview

This service predicts Enzyme Commission (EC) classifications using ESM embeddings and MaxSep selection.

## Features

- Supported input formats:
  - Amino acid sequence string
  - UniProt accession (resolved through the shared UniProt client)
  - FASTA file upload
  - FASTA content

## API endpoints

### POST /api/predict/ec

EC prediction endpoint (JSON input).

**Request body (JSON):**
```json
{
    "input_type": "sequence",
    "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
}
```

**Parameters:**
- `input_type` (required): Input type: `fasta`, `sequence`, or `uniprot`
- `query` (required): Query string (amino acid sequence, UniProt accession, or FASTA)

**Response:**
```json
{
    "result": {
        "ec_number": "EC:1.1.1.1, EC:1.1.1.2."
    }
}
```

### GET /health

Health check endpoint.

### GET /

Service information endpoint.

## Installation

```bash
cd services/ecnumber_predict
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```


## Running

```bash
python main.py
# Or
uvicorn main:app --host 0.0.0.0 --port 18902 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### Python client

```python
from client import ECNumberPredictionClient

client = ECNumberPredictionClient(base_url="http://localhost:18902")

# Predict EC numbers from a sequence
result = client.predict_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")
print(f"EC Number: {result['result']['ec_number']}")

# Use a UniProt accession
result = client.predict_uniprot("P12345")

# Use FASTA content
fasta_content = ">query\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
result = client.predict_fasta_content(fasta_content)
```

### curl

```bash
# Predict EC numbers from a sequence (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "sequence", "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'

# Use a UniProt accession (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "uniprot", "query": "P12345"}'

# Use FASTA content (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "fasta", "query": ">query\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'
```

## Directory layout

```
ecnumber_predict/
├── main.py              # FastAPI application
├── client.py            # API client
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   └── ecnumber_predictor.py  # EC prediction model
└── tests/
    ├── __init__.py
    └── test_api.py      # Tests
```

## Port

Default port: 18902

## External resources

- GMM model file (gmm_ensumble.pkl)
- Pretrained checkpoint (split100.pth)
- Training embeddings (100.pt)
- Training CSV (split100.csv)
- ESM extraction script (extract.py)
