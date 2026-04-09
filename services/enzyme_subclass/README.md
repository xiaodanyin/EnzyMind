# Enzyme Subclass Service - Enzyme Subclass Query Microservice

## Overview

The Enzyme Subclass Service queries enzyme subclass information from a local enzyme database, retrieving EC numbers, descriptions, catalytic activities, and associated UniProt IDs for specific enzyme classes.

## Port

- **Service port**: 18912

## Features

- Query subclass info by enzyme class name
- Supports multiple naming formats (case-insensitive)
- Random sampling with optional seed
- Markdown-formatted output
- Database statistics query
- Supports JSON and Form input formats

## Supported Enzyme Classes

| Enzyme Class | EC Prefix | Example Input |
|----------|---------|----------|
| Oxidoreductases | 1 | oxidoreductase, Oxidoreductases |
| Transferases | 2 | transferase, Transferases |
| Hydrolases | 3 | hydrolase, Hydrolases |
| Lyases | 4 | lyase, Lyases |
| Isomerases | 5 | isomerase, Isomerases |
| Ligases | 6 | ligase, Ligases |
| Translocases | 7 | translocase, Translocases |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/query/enzyme-subclass` | POST | Subclass query (JSON) |
| `/api/query/enzyme-subclass/form` | POST | Subclass query (form) |
| `/api/enzyme-classes` | GET | Get all enzyme class list |
| `/api/statistics` | GET | Get database statistics |
| `/query/enzyme-subclass` | POST | Legacy-compatible API |

## Installation

### 1. Create virtual environment

```bash
cd /path/to/Enzymind/services/enzyme_subclass
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Prepare data file

Ensure `data/enzy_database_processed.txt` exists. File format:

```text
ID   1.1.1.1
DE   Alcohol dehydrogenase.
CA   A primary alcohol + NAD(+) = an aldehyde + NADH.
DR   P00325, ADH1A_HUMAN; P00326, ADH1B_HUMAN;
//
```

### 4. Start service

```bash
python main.py
```

The service will start at http://localhost:18912.

## Usage Examples

### Health check

```bash
curl http://localhost:18912/health
```

Response:
```json
{
    "status": "healthy",
    "service": "enzyme_subclass",
    "version": "1.0.0"
}
```

### Get all enzyme classes

```bash
curl http://localhost:18912/api/enzyme-classes
```

Response:
```json
{
    "classes": {
        "Oxidoreductases": 1,
        "Transferases": 2,
        "Hydrolases": 3,
        "Lyases": 4,
        "Isomerases": 5,
        "Ligases": 6,
        "Translocases": 7
    }
}
```

### Query enzyme subclass (JSON format)

```bash
curl -X POST http://localhost:18912/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hydrolases",
    "num_samples": 3,
    "seed": 42
  }'
```

Response:
```json
{
    "success": true,
    "enzyme_class": "Hydrolases",
    "ec_prefix": 3,
    "result": "**Selected Hydrolases subclasses:**\n\n### EC number: 3.1.1.3\n...",
    "subclasses": [
        {
            "ID": "3.1.1.3",
            "DE": "Triacylglycerol lipase.",
            "CA": ["Triacylglycerol + H2O = diacylglycerol + a fatty acid."],
            "DR": ["P16233, LIPA_HUMAN", "Q06141, LIPC_HUMAN"]
        }
    ],
    "total_available": 3,
    "sampled": 3,
    "error": null,
    "valid_classes": null
}
```

### Query enzyme subclass (form format)

```bash
curl -X POST http://localhost:18912/api/query/enzyme-subclass/form \
  -d "query=oxidoreductase" \
  -d "num_samples=5" \
  -d "seed=42"
```

### Query using lowercase name

```bash
curl -X POST http://localhost:18912/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{"query": "transferase", "num_samples": 2}'
```

### Get database statistics

```bash
curl http://localhost:18912/api/statistics
```

Response:
```json
{
    "success": true,
    "total_entries": 17,
    "by_class": {
        "Oxidoreductases": {"ec_prefix": 1, "count": 3},
        "Transferases": {"ec_prefix": 2, "count": 3},
        "Hydrolases": {"ec_prefix": 3, "count": 3},
        "Lyases": {"ec_prefix": 4, "count": 2},
        "Isomerases": {"ec_prefix": 5, "count": 2},
        "Ligases": {"ec_prefix": 6, "count": 2},
        "Translocases": {"ec_prefix": 7, "count": 2}
    }
}
```

### Handle invalid input

```bash
curl -X POST http://localhost:18912/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{"query": "InvalidClass"}'
```

Response:
```json
{
    "success": false,
    "enzyme_class": null,
    "ec_prefix": null,
    "result": null,
    "subclasses": [],
    "error": "Invalid enzyme class name: InvalidClass",
    "valid_classes": ["Oxidoreductases", "Transferases", "Hydrolases", "Lyases", "Isomerases", "Ligases", "Translocases"]
}
```

## API Docs

After the service starts, visit the following URLs for interactive API documentation:

- **Swagger UI**: http://localhost:18912/docs
- **ReDoc**: http://localhost:18912/redoc

## Response Fields

### Subclass Query Response

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Query success |
| `enzyme_class` | string/null | Normalized enzyme class name |
| `ec_prefix` | int/null | EC number prefix (1-7) |
| `result` | string/null | Markdown-formatted result |
| `subclasses` | array | Subclass data list |
| `total_available` | int/null | Total available subclasses |
| `sampled` | int/null | Sampled count |
| `error` | string/null | Error message |
| `valid_classes` | array/null | Valid enzyme class names (only on invalid input) |

### Subclass Entry Structure

| Field | Type | Description |
|-------|------|-------------|
| `ID` | string | EC number |
| `DE` | string | Enzyme description |
| `CA` | array | Catalytic activity list |
| `DR` | array | UniProt ID list |

## Tests

Run unit tests:

```bash
source venv/bin/activate
pytest tests/ -v
```

## Data File Format

The data file uses the following format:

```text
ID   <EC number>
DE   <Enzyme description>
CA   <Catalytic activity 1>
CA   <Catalytic activity 2>
DR   <UniProt ID list, semicolon-separated>
//
```

`//` serves as the entry separator.

## License

MIT License
