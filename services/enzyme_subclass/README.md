# Enzyme Subclass Service

## Overview

This service retrieves enzyme subclasses from a local enzyme database, including EC numbers, descriptions, catalytic activities and associated UniProt accessions.

## Port

- **Service port**: 18912

## Features

- Look up subclasses by enzyme class name
- Accept multiple naming formats, case-insensitively
- Random sampling with an optional seed
- Markdown output
- Database statistics
- JSON and form inputs

## Supported enzyme classes

| Enzyme class | EC prefix | Example input |
|----------|---------|----------|
| Oxidoreductases | 1 | oxidoreductase, Oxidoreductases |
| Transferases | 2 | transferase, Transferases |
| Hydrolases | 3 | hydrolase, Hydrolases |
| Lyases | 4 | lyase, Lyases |
| Isomerases | 5 | isomerase, Isomerases |
| Ligases | 6 | ligase, Ligases |
| Translocases | 7 | translocase, Translocases |

## API endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/health` | GET | Health check |
| `/api/query/enzyme-subclass` | POST | Subclass query (JSON) |
| `/api/query/enzyme-subclass/form` | POST | Subclass query (form) |
| `/api/enzyme-classes` | GET | List enzyme classes |
| `/api/statistics` | GET | Database statistics |
| `/query/enzyme-subclass` | POST | Legacy API compatibility |

## Installation

### 1. Create a virtual environment

```bash
cd /path/to/EnzyMind/services/enzyme_subclass
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Prepare the data file

Ensure `data/enzy_database_processed.txt` exists. Its format is:

```text
ID   1.1.1.1
DE   Alcohol dehydrogenase.
CA   A primary alcohol + NAD(+) = an aldehyde + NADH.
DR   P00325, ADH1A_HUMAN; P00326, ADH1B_HUMAN;
//
```

### 4. Start the service

```bash
python main.py
```

The service runs at http://localhost:18912.

## Examples

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

### List enzyme classes

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

### Query enzyme subclasses (JSON)

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

### Query enzyme subclasses (form)

```bash
curl -X POST http://localhost:18912/api/query/enzyme-subclass/form \
  -d "query=oxidoreductase" \
  -d "num_samples=5" \
  -d "seed=42"
```

### Query with a lowercase class name

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

## API documentation

After starting the service, open the interactive API documentation:

- **Swagger UI**: http://localhost:18912/docs
- **ReDoc**: http://localhost:18912/redoc

## Response fields

### Subclass query response

| Field | Type | Description |
|------|------|------|
| `success` | boolean | Whether the query succeeded |
| `enzyme_class` | string/null | Normalized enzyme class name |
| `ec_prefix` | int/null | EC prefix (1–7) |
| `result` | string/null | Markdown result |
| `subclasses` | array | Subclass records |
| `total_available` | int/null | Total available subclasses |
| `sampled` | int/null | Number sampled |
| `error` | string/null | Error message |
| `valid_classes` | array/null | Valid class names, returned for invalid input |

### Subclass record

| Field | Type | Description |
|------|------|------|
| `ID` | string | EC number |
| `DE` | string | Enzyme description |
| `CA` | array | Catalytic activities |
| `DR` | array | UniProt accessions |

## Tests

Run unit tests:

```bash
source venv/bin/activate
pytest tests/ -v
```

## Data file format

The data file uses this format:

```text
ID   <EC number>
DE   <enzyme description>
CA   <catalytic activity 1>
CA   <catalytic activity 2>
DR   <semicolon-separated UniProt accessions>
//
```

`//` separates records.

## License

MIT License
