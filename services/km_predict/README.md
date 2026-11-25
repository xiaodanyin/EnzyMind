# Km Prediction Service

## Overview

This service predicts Michaelis constants (Km) with EITLEM, combining ESM protein sequence features with RDKit molecular features.

## Features

- Supported protein input formats:
  - Amino acid sequence string
  - UniProt accession (resolved through the shared UniProt client)
  - FASTA file upload
  - FASTA content
- Substrate molecules supplied as SMILES

## API endpoints

### POST /api/predict/km

Km prediction endpoint (form input).

**Parameters:**
- `smiles` (required): Substrate SMILES
- `enzyme_input_type` (required): Protein input type: `fasta`, `sequence`, or `uniprot`
- `enzyme_query` (optional): Protein sequence or UniProt accession
- `enzyme_file` (optional): FASTA file upload

**Response:**
```json
{
    "success": true,
    "km": 0.1234,
    "unit": "mM",
    "error": null
}
```

### POST /api/predict/km/simple

Simplified Km prediction endpoint (JSON input).

**Request body:**
```json
{
    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "enzyme_input": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ...",
    "enzyme_input_type": "sequence"
}
```

**Response:**
```json
{
    "success": true,
    "km": 0.1234,
    "unit": "mM"
}
```

### GET /health

Health check endpoint.

### GET /

Service information endpoint.

## Installation

```bash
cd services/km_predict
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
python main.py
# Or
uvicorn main:app --host 0.0.0.0 --port 18905 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### Python client

```python
from client import KmPredictClient

client = KmPredictClient(base_url="http://localhost:18905")

# Predict Km from a sequence
smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
result = client.predict_from_sequence(smiles, sequence)
print(f"Km: {result['km']} {result['unit']}")

# Use a UniProt accession
result = client.predict_from_uniprot(smiles, "P12345")

# Upload a FASTA file
result = client.predict_from_fasta_file(smiles, "/path/to/sequence.fasta")

# Simplified endpoint
result = client.predict_simple(smiles, sequence, "sequence")
```

### curl

```bash
# Predict Km from a sequence
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=sequence" \
    -F "enzyme_query=MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"

# Use a UniProt accession
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=uniprot" \
    -F "enzyme_query=P12345"

# Upload a FASTA file
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=fasta" \
    -F "enzyme_file=@sequence.fasta"

# Use the simplified JSON endpoint
curl -X POST "http://localhost:18905/api/predict/km/simple" \
    -H "Content-Type: application/json" \
    -d '{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "enzyme_input": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", "enzyme_input_type": "sequence"}'
```

## Directory layout

```
km_predict/
├── main.py              # FastAPI application
├── client.py            # API client
├── conftest.py          # pytest configuration
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── checkpoints/         # Model weights
├── models/
│   ├── __init__.py
│   ├── kinetics_predictor.py  # Km prediction model
│   └── utils.py         # Utility functions
└── tests/
    ├── __init__.py
    └── test_api.py      # Tests
```

## Port

Default port: 18905

## External resources

- Pretrained EITLEM weights (checkpoints directory)
- ESM-1v protein language model (esm1v_t33_650M_UR90S_1)
- RDKit for SMILES parsing and MACCS fingerprint generation

## Model overview

Km prediction uses EITLEM (Enzyme-substrate Interaction Transformer Learning for Enzyme kinetic parameter prediction):

1. **Protein features:** extract sequence embeddings with ESM-1v.
2. **Molecular features:** generate MACCS fingerprints with RDKit.
3. **Interaction modeling:** model enzyme–substrate interactions with multi-head attention.
4. **Output:** predicted Km in mM.

## Environment variables

- `KM_MODEL_PATH`: Custom model weights path (optional)

## Comparison with the kcat service

The Km and kcat services share a similar architecture, with these differences:

| Service | Port | Predicted parameter | Unit |
|------|------|----------|------|
| kcat_predict | 18904 | Turnover number kcat | s^-1 |
| km_predict | 18905 | Michaelis constant Km | mM |
