# Enzyme Type Recommendation Service

Enzyme type recommendation microservice for EnzyMind platform. This service uses RetroPlanner API to recommend enzyme types (EC numbers) for given chemical reactions.

## Features

- **Enzyme Type Recommendation**: Get EC number recommendations for reaction SMILES
- **Top-K Results**: Get top K recommendations with confidence scores
- **Multiple Output Formats**: JSON, formatted text, markdown table
- **Legacy API Support**: Backward compatible with original API

## Port

This service runs on port **18908**.

## Quick Start

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run Service

```bash
# Development
uvicorn main:app --reload --port 18908

# Production
uvicorn main:app --host 0.0.0.0 --port 18908
```

### Run Tests

```bash
pytest tests/ -v
```

## API Endpoints

### Health Check

```
GET /health
```

Returns service health status.

### Query Enzyme Type (JSON)

```
POST /api/query/enzyme-type
Content-Type: application/json

{
  "query": "CC(=O)O>>CCO"
}
```

Response:
```json
{
  "success": true,
  "reaction": "CC(=O)O>>CCO",
  "recommendations": [
    {"rank": 1, "ec_number": "1.1.1.1", "confidence": 0.95},
    {"rank": 2, "ec_number": "1.1.1.2", "confidence": 0.88}
  ]
}
```

### Query Enzyme Type (Form)

```
POST /api/query/enzyme-type/form
Content-Type: application/x-www-form-urlencoded

query=CC(=O)O>>CCO
```

### Get Top K Recommendations

```
POST /api/query/enzyme-type/top-k
Content-Type: application/json

{
  "query": "CC(=O)O>>CCO",
  "k": 5
}
```

### Get Formatted Output

```
POST /api/query/enzyme-type/formatted
Content-Type: application/json

{
  "query": "CC(=O)O>>CCO"
}
```

### Get Markdown Table

```
POST /api/query/enzyme-type/markdown
Content-Type: application/json

{
  "query": "CC(=O)O>>CCO"
}
```

Response:
```json
{
  "result": "| Rank | EC Number | Confidence |\n|------|-----------|------------|\n| 1 | 1.1.1.1 | 95.00% |\n| 2 | 1.1.1.2 | 88.00% |"
}
```

### Legacy Endpoint

```
POST /query/enzyme-type
Content-Type: application/json

{
  "query": "CC(=O)O>>CCO"
}
```

## Reaction SMILES Format

Reaction SMILES should follow the format: `reactants>>products`

Examples:
- Simple: `CC(=O)O>>CCO` (acetic acid to ethanol)
- Complex: `CC(=O)OCC>>CC(=O)O.CCO` (ethyl acetate hydrolysis)

## Client Usage

```python
from client import EnzymeTypeClient

client = EnzymeTypeClient("http://localhost:18908")

# Get recommendations
result = client.recommend("CC(=O)O>>CCO")
print(result)

# Get top EC number
top_ec = client.get_top_ec("CC(=O)O>>CCO")
print(f"Top EC: {top_ec}")

# Get markdown table
markdown = client.recommend_markdown("CC(=O)O>>CCO")
print(markdown)
```

## cURL Examples

```bash
# Health check
curl -X GET "http://localhost:18908/health"

# Query enzyme type (JSON input)
curl -X POST "http://localhost:18908/api/query/enzyme-type" \
    -H "Content-Type: application/json" \
    -d '{"query": "CC(=O)O>>CCO"}'

# Query enzyme type (form input)
curl -X POST "http://localhost:18908/api/query/enzyme-type/form" \
    -F "query=CC(=O)O>>CCO"

# Get Top K recommendations
curl -X POST "http://localhost:18908/api/query/enzyme-type/top-k" \
    -H "Content-Type: application/json" \
    -d '{"query": "CC(=O)O>>CCO", "k": 5}'

# Get formatted output
curl -X POST "http://localhost:18908/api/query/enzyme-type/formatted" \
    -H "Content-Type: application/json" \
    -d '{"query": "CC(=O)O>>CCO"}'

# Get Markdown table
curl -X POST "http://localhost:18908/api/query/enzyme-type/markdown" \
    -H "Content-Type: application/json" \
    -d '{"query": "CC(=O)O>>CCO"}'

# Legacy endpoint
curl -X POST "http://localhost:18908/query/enzyme-type" \
    -H "Content-Type: application/json" \
    -d '{"query": "CC(=O)O>>CCO"}'
```

## Project Structure

```
enzyme_type/
├── main.py                    # FastAPI application
├── client.py                  # Python client
├── conftest.py                # Pytest configuration
├── requirements.txt           # Dependencies
├── README.md                  # This file
├── models/
│   ├── __init__.py
│   └── enzyme_type_predictor.py  # Core prediction logic
└── tests/
    ├── __init__.py
    └── test_api.py            # API tests
```

## External Dependencies

This service relies on the RetroPlanner API:
- URL: `http://cadd.iddd.group/retroplanner/api/enzyme_recommender`
- Input: Reaction SMILES
- Output: EC numbers with confidence scores

## License

Part of the EnzyMind platform.
