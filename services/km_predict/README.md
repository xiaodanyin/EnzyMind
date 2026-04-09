# Km Prediction Service

## Introduction

Km Prediction Service is used to predict the Michaelis constant (Km) of enzymes. The service is based on the EITLEM model, combined with the ESM protein language model to extract sequence features and RDKit to extract molecular features for prediction.

## Features

- Support for multiple enzyme input formats:
  - Amino acid sequence string
  - UniProt ID (automatically retrieve sequence from UniProt)
  - FASTA file upload
  - FASTA format content
- Substrate molecules input in SMILES format

## API Endpoints

### POST /api/predict/km

Km prediction endpoint (form input).

**Parameters:**
- `smiles` (required): SMILES representation of substrate molecule
- `enzyme_input_type` (required): Enzyme input type, options: `fasta`, `sequence`, `uniprot`
- `enzyme_query` (optional): Enzyme sequence or UniProt ID
- `enzyme_file` (optional): FASTA file upload

**Return:**
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

**返回：**
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
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 18905 --reload
```

## Testing

```bash
pytest tests/ -v
```

## Usage Examples

### Using the Client

```python
from client import KmPredictClient

client = KmPredictClient(base_url="http://localhost:18905")

# Predict Km using sequence
smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
result = client.predict_from_sequence(smiles, sequence)
print(f"Km: {result['km']} {result['unit']}")

# Using UniProt ID
result = client.predict_from_uniprot(smiles, "P12345")

# Upload FASTA file
result = client.predict_from_fasta_file(smiles, "/path/to/sequence.fasta")

# Simplified interface
result = client.predict_simple(smiles, sequence, "sequence")
```

### Using curl

```bash
# Predict Km using sequence
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=sequence" \
    -F "enzyme_query=MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"

# Using UniProt ID
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=uniprot" \
    -F "enzyme_query=P12345"

# Upload FASTA file
curl -X POST "http://localhost:18905/api/predict/km" \
    -F "smiles=CC(=O)OC1=CC=CC=C1C(=O)O" \
    -F "enzyme_input_type=fasta" \
    -F "enzyme_file=@sequence.fasta"

# Using simplified JSON interface
curl -X POST "http://localhost:18905/api/predict/km/simple" \
    -H "Content-Type: application/json" \
    -d '{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "enzyme_input": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", "enzyme_input_type": "sequence"}'
```

## Directory Structure

```
km_predict/
├── main.py              # FastAPI application main file
├── client.py            # API client
├── conftest.py          # pytest configuration
├── requirements.txt     # Dependencies list
├── README.md            # Documentation
├── checkpoints/         # Model weight files
├── models/
│   ├── __init__.py
│   ├── kinetics_predictor.py  # Km predictor model
│   └── utils.py         # Utility functions
└── tests/
    ├── __init__.py
    └── test_api.py      # Test cases
```

## Port

Default port: 18905

## External Dependencies

- EITLEM pre-trained model weights (checkpoints directory)
- ESM1v protein language model (esm1v_t33_650M_UR90S_1)
- RDKit for molecular SMILES parsing and MACCS fingerprint generation

## Model Description

Km prediction is based on the EITLEM (Enzyme-substrate Interaction Transformer Learning for Enzyme kinetic parameter prediction) model:

1. **Protein Feature Extraction**: Use ESM1v model to extract embedding representation of protein sequences
2. **Molecular Feature Extraction**: Use RDKit to generate MACCS molecular fingerprints
3. **Interaction Modeling**: Model enzyme-substrate interactions through multi-head attention mechanism
4. **Prediction Output**: Output Km value (unit: mM)

## Environment Variables

- `KM_MODEL_PATH`: Custom model weights path (optional)

## Differences from Kcat Service

The Km prediction service has a similar structure to the Kcat prediction service, with the main differences being:

| Service | Port | Predicted Parameter | Unit |
|------|------|----------|------|
| kcat_predict | 18904 | Catalytic constant kcat | s^-1 |
| km_predict | 18905 | Michaelis constant Km | mM |
