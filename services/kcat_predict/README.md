# Kcat Prediction Service

## Introduction

Kcat Prediction Service is used to predict the catalytic constant (kcat) of enzymes. The service is based on the EITLEM model, combined with the ESM protein language model to extract sequence features and RDKit to extract molecular features for prediction.

## Features

- Support for multiple enzyme input formats:
  - Amino acid sequence string
  - UniProt ID (automatically retrieve sequence from UniProt)
  - FASTA file upload
  - FASTA format content
- Substrate molecules input in SMILES format

## API Endpoints

### POST /api/predict/kcat

Kcat prediction endpoint (form input).

**Parameters:**
- `smiles` (required): SMILES representation of substrate molecule
- `enzyme_input_type` (required): Enzyme input type, options: `fasta`, `sequence`, `uniprot`
- `enzyme_query` (optional): Enzyme sequence or UniProt ID
- `enzyme_file` (optional): FASTA file upload

**返回：**
```json
{
    "success": true,
    "kcat": 12.3456,
    "unit": "s^-1",
    "error": null
}
```

### POST /api/predict/kcat/simple

Simplified Kcat prediction endpoint (JSON input).

**Request body:**
```json
{
    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "enzyme_input": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ...",
    "enzyme_input_type": "sequence"
}
```

**返回：**
```json
{
    "success": true,
    "kcat": 12.3456,
    "unit": "s^-1"
}
```

### GET /health

Health check endpoint.

### GET /

Service information endpoint.

## Installation

```bash
cd services/kcat_predict
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 18904 --reload
```

## Testing

```bash
pytest tests/ -v
```

## Usage Examples

### Using the Client

```python
from client import KcatPredictClient

client = KcatPredictClient(base_url="http://localhost:18904")

# Predict kcat using sequence
smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
result = client.predict_from_sequence(smiles, sequence)
print(f"Kcat: {result['kcat']} {result['unit']}")

# Using UniProt ID
result = client.predict_from_uniprot(smiles, "P12345")

# Upload FASTA file
result = client.predict_from_fasta_file(smiles, "/path/to/sequence.fasta")

# Simplified interface
result = client.predict_simple(smiles, sequence, "sequence")
```

### Using curl

```bash
# Predict kcat using sequence
curl -X POST "http://localhost:18904/api/predict/kcat" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=sequence" \
    -F "enzyme_query=MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"

# Using UniProt ID
curl -X POST "http://localhost:18904/api/predict/kcat" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=uniprot" \
    -F "enzyme_query=P12345"

# Upload FASTA file
curl -X POST "http://localhost:18904/api/predict/kcat" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=fasta" \
    -F "enzyme_file=@sequence.fasta"

# Using simplified JSON interface
curl -X POST "http://localhost:18904/api/predict/kcat/simple" \
    -H "Content-Type: application/json" \
    -d '{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "enzyme_input": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", "enzyme_input_type": "sequence"}'
```

## Directory Structure

```
kcat_predict/
├── main.py              # FastAPI application main file
├── client.py            # API client
├── conftest.py          # pytest configuration
├── requirements.txt     # Dependencies list
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   ├── kinetics_predictor.py  # Kcat predictor model
│   └── utils.py         # Utility functions
└── tests/
    ├── __init__.py
    └── test_api.py      # Test cases
```

## Port

Default port: 18904

## External Dependencies

- EITLEM pre-trained model weights
- ESM1v protein language model (esm1v_t33_650M_UR90S_1)
- RDKit for molecular SMILES parsing and MACCS fingerprint generation

## Model Description

Kcat prediction is based on the EITLEM (Enzyme-substrate Interaction Transformer Learning for Enzyme kinetic parameter prediction) model:

1. **Protein Feature Extraction**: Use ESM1v model to extract embedding representation of protein sequences
2. **Molecular Feature Extraction**: Use RDKit to generate MACCS molecular fingerprints
3. **Interaction Modeling**: Model enzyme-substrate interactions through multi-head attention mechanism
4. **Prediction Output**: Output kcat value (unit: s^-1)

## Environment Variables

- `KCAT_MODEL_PATH`: Custom model weights path (optional)
