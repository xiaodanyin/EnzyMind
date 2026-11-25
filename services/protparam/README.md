# Protein Physicochemical Properties Service

Protein property calculations using ExPASy ProtParam, with a local Biopython fallback when the remote service is unavailable or incomplete.

## Features

- **Protein properties:** calculate sequence-derived physicochemical parameters
- **Multiple outputs:** molecular weight, theoretical pI, instability index and GRAVY
- **Protein inputs:** amino acid sequence, UniProt accession or FASTA
- **Request formats:** JSON, form fields or file upload
- **Structured results:** original text, Markdown and parsed parameter values

## Calculated parameters

The service returns these physicochemical properties:

| Parameter | Description |
|------|------|
| Number of amino acids | Residue count |
| Molecular weight | Molecular weight (Da) |
| Theoretical pI | Theoretical isoelectric point |
| Instability index | Sequence-derived instability index |
| Grand average of hydropathicity (GRAVY) | Mean residue hydropathicity |

## Quick start

### Install dependencies

```bash
cd services/protparam
pip install -r requirements.txt
```

### Start the service

```bash
python main.py
```

The service listens on `http://0.0.0.0:18909`.

## API endpoints

The direct service response below exposes `parameters` at the top level. Gateway calls to `/api/query/protein-physchem` or `/api/query/protein-params` use the compatibility response: read `data.parameters`, with the readable report in `result`.

### Health check

```http
GET /health
```

**Example response:**
```json
{
  "status": "healthy",
  "service": "protparam"
}
```

### Protein property analysis (JSON)

```http
POST /api/query/protein-physchem
Content-Type: application/json
```

**Request parameters:**
| Parameter | Type | Required | Description |
|------|------|------|------|
| query | string | Yes | Protein sequence, UniProt accession or FASTA |

**Example requests:**

Amino acid sequence:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTISSWFAGVTGSWIAALWQ"}'
```

UniProt accession:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": "P12345"}'
```

FASTA:
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem" \
     -H "Content-Type: application/json" \
     -d '{"query": ">sp|P12345|Example\nMKFLILLFNILCLFPVLAADNHGVGPQ"}'
```

**Example response (illustrative values):**
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

### Protein property analysis (form)

```http
POST /api/query/protein-physchem/form
Content-Type: application/x-www-form-urlencoded
```

**Example request:**
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem/form" \
     -d "query=MKFLILLFNILCLFPVLAADNHGVGPQ"
```

### Protein property analysis (file upload)

```http
POST /api/query/protein-physchem/file
Content-Type: multipart/form-data
```

**Example request:**
```bash
curl -X POST "http://localhost:18909/api/query/protein-physchem/file" \
     -F "file=@protein.fasta"
```

### Legacy endpoint

```http
POST /query/protein-physchem
```

Retains compatibility with older clients and uses the same parameters as the JSON endpoint.

## Supported input formats

### 1. Amino acid sequence

Supply an amino acid sequence directly:

```
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTISSWFAGVTGSWIAALWQ
```

### 2. UniProt ID

Supply a standard UniProt accession:

```
P12345
Q9Y6K9
```

The shared UniProt client resolves the sequence locally first, with official API fallback.

### 3. FASTA

Standard FASTA format:

```
>sp|P12345|EXAMPLE_HUMAN Example protein
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLNNLGYTIS
SWFAGVTGSWIAALWQ
```

## Configuration

Default settings:

| Parameter | Default | Description |
|------|--------|------|
| HOST | 0.0.0.0 | Bind address |
| PORT | 18909 | Service port |

## Dependencies

- **fastapi:** web framework
- **uvicorn:** ASGI server
- **requests:** HTTP client
- **beautifulsoup4:** HTML parsing
- **pydantic:** data validation
- **python-multipart:** file uploads

## Tests

```bash
cd services/protparam
pytest tests/ -v
```

## Project layout

```
protparam/
├── main.py                  # FastAPI application
├── requirements.txt         # Dependencies
├── README.md                # This document
├── models/
│   ├── __init__.py
│   └── protparam_analyzer.py # ProtParam analysis
└── tests/
    ├── __init__.py
    └── test_api.py          # API tests
```

## Error handling

Analysis failures use the following response shape; request validation can also return a 4xx status:

```json
{
  "success": false,
  "error": "Description of the analysis failure"
}
```

Typical failure causes:
- Empty sequence input
- Invalid residues or multiple FASTA records
- UniProt lookup failure when no usable local sequence exists
- ExPASy unavailability triggers local calculation; the result identifies its source and fallback reason

## Analysis workflow

The analysis follows these steps:

1. **Parse input:** detect a sequence, UniProt accession or FASTA record.
2. **Resolve sequence:** retrieve accession inputs through the shared local-first UniProt client.
3. **Validate sequence:** normalize case and whitespace; reject invalid residues instead of silently deleting them. Select one FASTA record rather than concatenating proteins.
4. **Calculate properties:** submit to ExPASy ProtParam, with Biopython fallback for unavailable or incomplete responses.
5. **Parse results:** extract the calculated properties and identify their source.
6. **Format output:** return Markdown and structured JSON.

## Attribution

This service uses ExPASy ProtParam and Biopython for sequence-derived calculations. These values are not experimental measurements.

- ExPASy: https://www.expasy.org/
- ProtParam: https://web.expasy.org/protparam/

UniProt accession inputs use `shared/uniprot.py`: verified HTTPS with a scoped
TLS 1.2 adapter, bounded retries (60 seconds), validated FASTA and a 6-hour,
128-entry/4 MiB memory cache. Raw sequence and FASTA inputs retain their existing
behavior. No TLS certificate verification is disabled.

ExPASy requests have a 5-second connect / 20-second read timeout. On timeout,
unusable HTML, or mismatched sequence length, core properties are calculated
locally with Biopython 1.86 (average molecular mass, pI, instability index,
Kyte–Doolittle GRAVY and residue composition). The `source`, `fallback_reason`
and rendered report explicitly distinguish this result from ExPASy; reference
tables can produce small numeric differences. Extra ExPASy-only report fields
are not fabricated. Both structured and legacy endpoints preserve their usual
fields and expose the provenance. Reference: https://biopython.org/docs/1.86/api/Bio.SeqUtils.ProtParam.html
