# Substrate Prediction Service

## Introduction

Substrate Prediction Service is used to predict whether there is an enzyme-substrate relationship between a given enzyme and molecule. The service is based on the MEI (Molecular Enzyme Interaction) model, combining ESM protein embeddings and molecular graph neural networks for prediction.

## Features

- Support for multiple enzyme input formats:
  - Amino acid sequence string
  - UniProt ID (automatically fetch sequence from UniProt)
  - FASTA format content

- Molecular input:
  - SMILES string

## API Endpoints

### POST /api/predict/substrate

Substrate prediction endpoint (JSON format input).

**Request Body (JSON):**
```json
{
    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "enzyme_input_type": "sequence",
    "enzyme_query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
}
```

**Parameter Description:**
- `smiles` (required): SMILES string of substrate molecule
- `enzyme_input_type` (required): Enzyme input type, options: `fasta`, `sequence`, `uniprot`
- `enzyme_query` (required): Enzyme query string (amino acid sequence, UniProt ID or FASTA format content)

**Return:**
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
# or venv\Scripts\activate  # Windows
bash ./install_torch.sh
bash .install_dgl.sh
pip install -r requirements.txt
```

## Running

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 18903 --reload
```

## Testing

```bash
pytest tests/ -v
```

## Usage Examples

### Using the Client

```python
from client import SubstratePredictionClient

client = SubstratePredictionClient(base_url="http://localhost:18903")

# Predict with sequence
result = client.predict_with_sequence(
    smiles="CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
    sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ..."
)
print(f"Is substrate: {result['result']['is_substrate']}")
print(f"Confidence: {result['result']['confidence']}")

# Predict with UniProt ID
result = client.predict_with_uniprot(
    smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
    uniprot_id="P12345"
)
```

### Using curl

```bash
# Predict with sequence
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "sequence",
        "enzyme_query": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    }'

# Predict with UniProt ID
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "uniprot",
        "enzyme_query": "P12345"
    }'

# Predict with FASTA format content
curl -X POST "http://localhost:18903/api/predict/substrate" \
    -H "Content-Type: application/json" \
    -d '{
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "enzyme_input_type": "fasta",
        "enzyme_query": ">my_enzyme\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    }'
```

## Directory Structure

```
substrate_predict/
├── main.py              # FastAPI application main file
├── client.py            # API client
├── requirements.txt     # Dependencies list
├── README.md            # Documentation
├── models/
│   ├── __init__.py
│   ├── substrate_predictor.py  # Substrate predictor model
│   ├── mol_gnn.py              # Molecular graph neural network
│   └── graph_dataset.py        # Graph dataset processing
└── tests/
    ├── __init__.py
    └── test_api.py      # Test cases
```

## Port

Default port: 18903

## Model Description

### MEI Model

MEI (Molecular Enzyme Interaction) model is a deep learning model for predicting enzyme-substrate relationships:

1. **Enzyme Embedding Processing**: Use ESM1b to extract protein sequence embeddings, then apply LayerNormNet for dimensionality reduction
2. **Molecular Embedding**: Use Graph Neural Network (GNN) to extract molecular features from SMILES strings
3. **Interaction Prediction**: Fuse enzyme and molecular features through attention mechanism, finally predict whether enzyme-substrate relationship exists

### Dependent Model Files

- `model.pt`: MEI main model weights
- `mol_ra/saved_3/gcn_1024/`: Molecular GNN model and feature encoder
- `split100.pth`: Enzyme embedding processing model weights
