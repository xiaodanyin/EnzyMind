# EC Number Prediction Service

## Overview

The EC Number Prediction Service predicts Enzyme Commission (EC) numbers for proteins using ESM embeddings and the MaxSep method.

## Features

- Supported input types:
  - Amino acid sequence string
  - UniProt ID (sequence is fetched automatically)
  - FASTA file upload
  - FASTA-formatted content

## API Endpoints

### POST /api/predict/ec

EC number prediction (JSON input).

**Request body (JSON):**
```json
{
    "input_type": "sequence",  // options: fasta, sequence, uniprot
    "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
}
```

**Parameters:**
- `input_type` (required): `fasta`, `sequence`, or `uniprot`
- `query` (required): amino acid sequence, UniProt ID, or FASTA content

**Response:**
```json
{
    "result": {
        "ec_number": "EC:1.1.1.1, EC:1.1.1.2."
    }
}
```

### GET /health

Health check.

### GET /

Service info.

## Installation

```bash
cd services/ecnumber_predict
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Run

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 18902 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Usage Examples

### Python client

```python
from client import ECNumberPredictionClient

client = ECNumberPredictionClient(base_url="http://localhost:18902")

# Predict EC number for a sequence
result = client.predict_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")
print(f"EC Number: {result['result']['ec_number']}")

# Using UniProt ID
result = client.predict_uniprot("P12345")

# Using FASTA content
fasta_content = ">query\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
result = client.predict_fasta_content(fasta_content)
```

### curl

```bash
# Predict EC number for a sequence (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "sequence", "query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'

# Using UniProt ID (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "uniprot", "query": "P12345"}'

# Using FASTA content (JSON)
curl -X POST "http://localhost:18902/api/predict/ec" \
    -H "Content-Type: application/json" \
    -d '{"input_type": "fasta", "query": ">query\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"}'
```

## Directory Structure

```
ecnumber_predict/
├── main.py              # FastAPI app entry
├── client.py            # API client
├── requirements.txt     # dependencies
├── README.md            # documentation
├── models/
│   ├── __init__.py
│   └── ecnumber_predictor.py  # EC number predictor model
└── tests/
    ├── __init__.py
    └── test_api.py      # test cases
```

## Port

Default port: 18902

## External Resources

- GMM model file (gmm_ensumble.pkl)
- Pretrained checkpoint (split100.pth)
- Training embeddings (100.pt)
- Training CSV (split100.csv)
- ESM extraction script (extract.py)
