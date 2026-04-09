# ProtParam - Protein Physicochemical Property Analysis Service

A protein physicochemical property analysis microservice based on ExPASy ProtParam.

## Features

- 🧬 **Protein Physicochemical Property Analysis**: Calculate various physicochemical parameters of proteins
- 📊 **Multi-Parameter Output**: Molecular weight, isoelectric point, instability coefficient, GRAVY, etc.
- 🔀 **Multiple Input Format Support**: Support amino acid sequences, UniProt IDs, FASTA format
- 📁 **Multiple Interface Forms**: Support JSON, forms, file uploads and other calling methods
- 🎯 **Structured Data**: Provide raw text, Markdown and parsed parameter values simultaneously

## Analysis Parameters

The service returns the following physicochemical property parameters:

| Parameter | Description |
|------|------|
| Number of amino acids | Number of amino acids |
| Molecular weight | Molecular weight (Da) |
| Theoretical pI | Theoretical isoelectric point |
| Instability index | Instability coefficient |
| Grand average of hydropathicity (GRAVY) | Average hydropathicity |

## Quick Start

### Install Dependencies

```bash
cd services/protparam
pip install -r requirements.txt
```

### Start Service

```bash
python main.py
```

The service will start at `http://0.0.0.0:18909`.

## API Endpoints

### Health Check

```http
GET /health
```

**Response Example:**
```json
{
  "status": "healthy",
  "service": "protparam"
}
```

### Protein Physicochemical Property Analysis (JSON)

```http
POST /api/query/protein-physchem
Content-Type: application/json
```

**Request Parameters:**
| Parameter | Type | Required | Description |
|------|------|------|------|
| query | string | Yes | Protein sequence, UniProt ID or FASTA format |

**Request Example:**

Using amino acid sequence:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTISSWFAGVTGSWIAALWQ"}'
```

Using UniProt ID:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": "P12345"}'
```

Using FASTA format:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": ">sp|P12345|Example\nMKFLILLFNILCLFPVLAADNHGVGPQ"}'
```

**Response Example:**
```json
{
  "success": true,
  "sequence_length": 75,
  "markdown": "## ProtParam Results\n\n- Number of amino acids: 75\n- Molecular weight: 8143.49\n- Theoretical pI: 4.52\n- Instability index (II) is computed to be 42.08\n- Grand average of hydropathicity (GRAVY): 0.628\n",
  "raw_text": "Number of amino acids: 75\nMolecular weight: 8143.49\n...",
  "parameters": {
    "num_amino_acids": 75,
    "molecular_weight": 8143.49,
    "theoretical_pi": 4.52,
    "instability_index": 42.08,
    "gravy": 0.628
  }
}
```

### Protein Physicochemical Property Analysis (Form)

```http
POST /api/query/protein-physchem/form
Content-Type: application/x-www-form-urlencoded
```

**Request Example:**
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem/form" \
     -d "query=MKFLILLFNILCLFPVLAADNHGVGPQ"
```

### Protein Physicochemical Property Analysis (File Upload)

```http
POST /api/query/protein-physchem/file
Content-Type: multipart/form-data
```

**Request Example:**
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem/file" \
     -F "file=@protein.fasta"
```

### Legacy Compatible Endpoint

```http
POST /query/protein-physchem
```

Maintains compatibility with previous versions. Parameters are the same as the JSON endpoint.

## Input Format Support

### 1. Amino Acid Sequence

Enter amino acid sequence string directly:

```
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTISSWFAGVTGSWIAALWQ
```

### 2. UniProt ID

Enter standard UniProt ID:

```
P12345
Q9Y6K9
```

The service will automatically fetch the corresponding protein sequence from UniProt API.

### 3. FASTA Format

Standard FASTA format:

```
>sp|P12345|EXAMPLE_HUMAN Example protein
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTIS
SWFAGVTGSWIAALWQ
```

## Configuration

The service uses the following default configuration:

| Parameter | Default Value | Description |
|------|--------|------|
| HOST | 0.0.0.0 | Listen address |
| PORT | 18909 | Service port |

## Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **requests**: HTTP client
- **beautifulsoup4**: HTML parsing
- **pydantic**: Data validation
- **python-multipart**: File upload support

## Testing

```bash
cd services/protparam
pytest tests/ -v
```

## Project Structure

```
protparam/
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Dependencies
├── README.md               # This file
├── models/
│   ├── __init__.py
│   └── protparam_analyzer.py  # ProtParam analyzer
└── tests/
    ├── __init__.py
    └── test_api.py          # API tests
```

## Error Handling

The service returns error responses in a unified format when an error is encountered:

```json
{
  "success": false,
  "error": "Error description message"
}
```

Common errors:
- `Empty sequence provided`: Empty sequence input
- `No valid amino acids found`: Invalid sequence format
- `Failed to fetch sequence from UniProt`: Unable to fetch sequence from UniProt
- `Failed to get response from ExPASy`: ExPASy service request failed

## Technical Principle

This service analyzes proteins through the following steps:

1. **Input Parsing**: Automatically identify input type (sequence/UniProt ID/FASTA)
2. **Sequence Retrieval**: If UniProt ID, fetch sequence from UniProt API
3. **Sequence Cleaning**: Remove non-amino acid characters
4. **ExPASy Request**: Submit sequence to ExPASy ProtParam service
5. **Result Parsing**: Extract physicochemical property parameters from HTML response
6. **Format Conversion**: Convert to Markdown and structured JSON format

## Copyright Notice

This service uses ExPASy ProtParam service for protein analysis.

- ExPASy: https://www.expasy.org/
- ProtParam: https://web.expasy.org/protparam/
