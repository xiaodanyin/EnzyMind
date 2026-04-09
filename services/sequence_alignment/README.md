# Sequence Alignment Service (BLAST)

Protein sequence alignment microservice using NCBI BLAST for sequence search.

## Port

**18910**

## Installation

```bash
cd /path/to/Enzymind/services/sequence_alignment

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Service

```bash
# Development mode
uvicorn main:app --reload --port 18910

# Production mode
uvicorn main:app --host 0.0.0.0 --port 18910
```

## Running Tests

```bash
pytest tests/ -v
```

## API Endpoints

### Health Check

```bash
curl http://localhost:18910/health
```

Response:
```json
{"status": "healthy", "service": "sequence_alignment"}
```

### BLAST Search (JSON)

```bash
curl -X POST http://localhost:18910/api/query/blast \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "max_results": 3
  }'
```

Response:
```json
{
  "success": true,
  "query_length": 52,
  "num_results": 3,
  "alignments": [
    {
      "title": "sp|P12345|TEST_HUMAN Test protein",
      "length": 500,
      "e_value": 1e-50,
      "score": 200,
      "query": "MKFLILLFNILCLFPVLAADNHGVGPQ...",
      "match": "MKFLILLFNILCLFPVLAADNHGVGPQ...",
      "subject": "MKFLILLFNILCLFPVLAADNHGVGPQ..."
    }
  ]
}
```

### Using Form Input

```bash
curl -X POST http://localhost:18910/api/query/blast/form \
  -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
  -F "max_results=3"
```

### Upload FASTA File

```bash
curl -X POST http://localhost:18910/api/query/blast/file \
  -F "file=@protein.fasta" \
  -F "max_results=3"
```

### HTML Format Output

```bash
curl -X POST http://localhost:18910/api/query/blast/html \
  -H "Content-Type: application/json" \
  -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'
```

### Markdown Format Output

```bash
curl -X POST http://localhost:18910/api/query/blast/markdown \
  -H "Content-Type: application/json" \
  -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'
```

### Legacy API Compatibility

```bash
curl -X POST http://localhost:18910/query/blast \
  -F "input_type=sequence" \
  -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
  -F "max_results=3"
```

## Supported Input Types

- Raw amino acid sequence
- UniProt ID (e.g., P12345)
- FASTA format content
- FASTA file upload

## Parameter Description

| Parameter | Type | Default | Description |
|------|------|--------|------|
| query | string | Required | Protein sequence, UniProt ID or FASTA |
| max_results | int | 3 | Maximum number of results (1-50) |

## Project Structure

```
sequence_alignment/
├── main.py                  # FastAPI application
├── requirements.txt         # Dependencies
├── README.md                # This file
├── models/
│   ├── __init__.py
│   └── blast_searcher.py    # BLAST search logic
└── tests/
    ├── __init__.py
    └── test_api.py          # API tests
```

## External Dependencies

- NCBI BLAST: https://blast.ncbi.nlm.nih.gov/
- Biopython: For interaction with NCBI BLAST

## Notes

- BLAST search may take a long time (30-60 seconds)
- Default timeout is set to 60 seconds
- E-value threshold default is 0.01

## License

Part of the EnzyMind platform.
