# Substrate Determination Service

## Overview

This service predicts enzyme–substrate compatibility with the MEI (Molecular Enzyme Interaction) model, combining ESM protein embeddings with a molecular graph neural network.

## Features

- Supported protein input formats:
  - Amino acid sequence string
  - UniProt accession (resolved through the shared UniProt client)
  - FASTA content

- Molecular input:
  - SMILES string

## API endpoints

### POST /api/predict/substrate

Substrate prediction endpoint (JSON input).

**Request body (JSON):**
```json
{
    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "enzyme_input_type": "sequence",
    "enzyme_query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
}
```

**Parameters:**
- `smiles` (required): Substrate SMILES
- `enzyme_input_type` (required): Protein input type: `fasta`, `sequence`, or `uniprot`
- `enzyme_query` (required): Protein query (amino acid sequence, UniProt accession, or FASTA)

**Response:**
```json
{
    "result": {
        "is_substrate": true,
        "confidence": 0.8765
    }
}
```

### GET /health

Health check endpoint.

### GET /

Service information endpoint.

## Installation

```bash
cd services/substrate_predict
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
bash ./install_torch.sh
bash .install_dgl.sh
pip install -r requirements.txt
```



## Running

```bash
python main.py
# Or
uvicorn main:app --host 0.0.0.0 --port 18903 --reload
```

## Tests

```bash
pytest tests/ -v
```

## Examples

### Python client

```python
from client import SubstratePredictionClient

client = SubstratePredictionClient(base_url="http://localhost:18903")

# Predict from a sequence
result = client.predict_with_sequence(
    smiles="CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
    sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
)
print(f"Is substrate: {result['result']['is_substrate']}")
print(f"Confidence: {result['result']['confidence']}")

# Predict from a UniProt accession
result = client.predict_with_uniprot(
    smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
    uniprot_id="P12345"
)
```

### curl

```bash
# Predict from a sequence
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "sequence",
        "enzyme_query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    }'

# Predict from a UniProt accession
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "uniprot",
        "enzyme_query": "P12345"
    }'

# Predict from FASTA content
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "fasta",
        "enzyme_query": ">my_enzyme\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    }'
```

## Directory layout

```
substrate_predict/
├── main.py              # FastAPI application
├── client.py            # API client
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   ├── substrate_predictor.py  # Substrate compatibility model
│   ├── mol_gnn.py              # Molecular graph neural network
│   └── graph_dataset.py        # Graph dataset processing
└── tests/
    ├── __init__.py
    └── test_api.py      # Tests
```

## Port

Default port: 18903

## Model overview

### MEI model

MEI (Molecular Enzyme Interaction) is a deep learning model for enzyme–substrate compatibility:

1. **Protein embeddings:** extract ESM-1b sequence embeddings and reduce their dimensionality with LayerNormNet.
2. **Molecular embeddings:** extract molecular features from SMILES with a graph neural network (GNN).
3. **Interaction prediction:** combine protein and molecular features through attention to predict compatibility.

### Required model files

- `model.pt`: Main MEI model weights
- `mol_ra/saved_3/gcn_1024/`: Molecular GNN model and feature encoders
- `split100.pth`: Protein embedding model weights
