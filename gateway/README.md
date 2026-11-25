# EnzyMind API Gateway

API Gateway server for routing frontend requests to EnzyMind microservices.

## Overview

This FastAPI server:

- Proxies API requests to appropriate microservices (ports 18901–18919)
- Manages workspace identities, conversations, tool budgets and saved results
- Handles CORS for the Vue frontend
- Serves PDB files from structure prediction outputs
- Provides unified API endpoints with `/api` and `/enzymind/api` prefixes

## Installation

```bash
cd gateway
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

Run from the repository root, or use `bash scripts/start_web.sh start` to load the deployment environment automatically:

```bash
# Development
gateway/venv/bin/python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --no-proxy-headers --reload

# Production
gateway/venv/bin/python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --workers 1 --no-proxy-headers
```

Use one gateway worker with the existing startup script: it owns the background
Agent tasks and BLAST submission recovery. BLAST retrieval leases are stored in
SQLite, but a newly starting gateway must not recover another worker's in-flight
submission. Scale scientific services independently.

### Saved BLAST searches

For explicitly selected remote NCBI databases, browser and Agent BLAST requests return a saved `submitting` / `queued` record
without holding a connection open for the NCBI queue. The gateway retrieves the
same RID in the background, updates the same result, and recovers historical queue
timeouts on startup. `POST /api/workspace/results/{id}/refresh` requires the
original workspace key and resumes retrieval only. Jobs pause checks after 24
hours; the original 90-day retention deadline is unchanged. See the
[BLAST service API and recovery contract](../services/sequence_alignment/README.md).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENZYMIND_HOST` | `localhost` | Host where microservices run |

---

## API Endpoints Reference

### Service Port Mapping

| Port | Service Name | Description |
|------|--------------|-------------|
| 18901 | enzy_recognize | Enzyme/non-enzyme prediction |
| 18902 | ecnumber_predict | EC classification prediction |
| 18903 | substrate_predict | Substrate compatibility prediction |
| 18904 | kcat_predict | Kcat prediction |
| 18905 | km_predict | Km prediction |
| 18906 | structure_predict | Protein structure prediction (ESMFold) |
| 18907 | active_sites | Functional-site prediction (EasIFA) |
| 18908 | enzyme_type | Enzyme class recommendation |
| 18909 | protparam | Protein physicochemical properties |
| 18910 | sequence_alignment | BLAST sequence alignment |
| 18911 | function_get | Protein function queries |
| 18912 | enzyme_subclass | Enzyme subclass queries |
| 18913 | ec_reaction_info | Catalytic-activity queries |
| 18914 | enzyme_check | Annotated enzyme status (UniProt) |
| 18915 | enzyme_full_info | Integrated enzyme information |
| 18916 | functional_site | Annotated functional sites |
| 18917 | kinetic_params | Reported kinetic parameters |
| 18918 | sequence_info | Sequence information |
| 18919 | query_mechanism_mcsa | M-CSA enzyme records and mechanisms |

---

## API usage examples

The public API base is `https://cadd.zju.edu.cn/enzymind/api/`. Responses below illustrate payload shapes; their values are not verified results for the example accessions. Optional provenance and workspace fields may also be present. For M-CSA endpoints, see the [service reference](../services/query_mechanism_mcsa/README.md); for authenticated Agent/results APIs, see [Workspace v2](../agent_n8n/workspace/README.md).

### 1. Enzyme Recognition (Port 18901)

**Predict whether a protein is an enzyme.**

```bash
# Direct to service
curl -X POST http://localhost:18901/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST http://localhost:18901/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST https://cadd.zju.edu.cn/enzymind/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative response:**
```json
{
  "result": {
    "is_enzyme": true,
    "confidence": 0.9542
  }
}
```

**Input Types**: `sequence` | `fasta` | `uniprot`

---

### 2. EC Number Prediction (Port 18902)

**Predict protein EC classifications.**

```bash
# Direct to service
curl -X POST http://localhost:18902/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST http://localhost:18902/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative response:**
```json
{
  "result": {
    "ec_number": "3.4.21.4"
  }
}
```

---

### 3. Substrate Prediction (Port 18903)

**Predict compatibility between an enzyme and a molecule.**

```bash
# Direct to service
curl -X POST http://localhost:18903/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'

curl -X POST http://localhost:18903/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "sequence",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "sequence",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative response:**
```json
{
  "result": {
    "is_substrate": true,
    "confidence": 0.8765
  }
}
```

---

### 4. Kcat Prediction (Port 18904)

**Predict the catalytic turnover number, kcat.**

```bash
# Direct to service
curl -X POST http://localhost:18904/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'
curl -X POST http://localhost:18904/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Via gateway (default enzyme_input_type="sequence")
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "kcat": 12.3456,
  "unit": "s^-1",
  "error": null
}
```

---

### 5. Km Prediction (Port 18905)

**Predict the Michaelis constant, Km.**

```bash
# Direct to service
curl -X POST http://localhost:18905/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'
curl -X POST http://localhost:18905/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "km": 0.5432,
  "unit": "mM",
  "error": null
}
```

---

### 6. Structure Prediction (Port 18906)

**Predict protein 3D coordinates with ESMFold.**

```bash
# Direct to service - basic prediction
curl -X POST http://localhost:18906/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "input_type": "sequence",
    "output_name": "my_protein"
  }'
curl -X POST http://localhost:18906/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "input_type": "uniprot"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "input_type": "sequence",
    "output_name": "my_protein"
  }'
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "input_type": "uniprot"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "pdb_path": "/tmp/esmfold_output/my_protein.pdb",
  "static_path": "/static/pdb/my_protein.pdb",
  "sequence": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
  "sequence_length": 52,
  "error": null
}
```

**Download PDB file directly**:
```bash
# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/structure/download \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "input_type": "uniprot"
  }' -o protein.pdb
```

**Upload FASTA file**:
```bash
# Direct to service
curl -X POST http://localhost:18906/api/predict/structure/file \
  -F "file=@protein.fasta" \
  -F "output_name=my_protein"

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/structure/file \
  -F "file=@protein.fasta"
```

**Form input**:
```bash
curl -X POST http://localhost:18906/api/predict/structure/form \
  -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
  -F "input_type=sequence"
```

**Check configuration**:
```bash
curl http://localhost:18906/api/config
```

**Illustrative response:**
```json
{
  "configured": true,
  "issues": [],
  "output_dir": "/tmp/esmfold_output",
  "docker_image": "biochunan/esmfold-image:nonroot-runtime",
  "use_gpu": true
}
```

---

### 7. Active Sites Prediction (Port 18907)

**Predict functional sites with EasIFA (asynchronous processing).**

Private jobs require the same cookie or `X-Easifa-Session` when submitting, polling and retrieving results. Set `ENZYMIND_EASIFA_COOKIE_SECURE=false` for local HTTP use; retain the default `true` behind production HTTPS. Cookie files are access credentials: keep them private and out of Git. The same rules apply through the Gateway, which preserves sessions for GET and upload requests.

```bash
# Prepare a persistent private cookie jar (reuse it for subsequent calls).
umask 077
mkdir -p "$HOME/.local/state/enzymind"
cookie_jar="$HOME/.local/state/enzymind/api.cookies"

# Submit job with UniProt ID
curl -b "$cookie_jar" -c "$cookie_jar" -X POST http://localhost:18907/api/predict/active-sites/submit/uniprot \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345",
    "use_celery": true
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "job_id": "abc-123-xyz",
  "task_manager": "celery",
  "input_type": "uniprot",
  "error": null
}
```

```bash
# Check job status
curl -b "$cookie_jar" -c "$cookie_jar" http://localhost:18907/api/predict/active-sites/job/abc-123-xyz

# Response
{
  "success": true,
  "status": "completed",  # pending | running | completed | failed
  "data": {...},
  "error": null
}

# Get results
curl -b "$cookie_jar" -c "$cookie_jar" http://localhost:18907/api/predict/active-sites/results/abc-123-xyz

# Response
{
  "success": true,
  "data": {
    "active_sites": [
      {"position": 45, "residue": "H", "confidence": 0.95}
    ]
  },
  "markdown": "| Position | Residue | Confidence |\n|---|---|---|\n| 45 | H | 0.95 |",
  "error": null
}
```

**Submit with amino acid sequence**:
```bash
curl -b "$cookie_jar" -c "$cookie_jar" -X POST http://localhost:18907/api/predict/active-sites/submit/sequence \
  -H "Content-Type: application/json" \
  -d '{
    "aa_sequence": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "rxn_smiles": "CC(=O)O>>CCO",
    "use_celery": true
  }'
```

**Submit with PDB structure file**:
```bash
curl -b "$cookie_jar" -c "$cookie_jar" -X POST http://localhost:18907/api/predict/active-sites/submit/structure \
  -F "pdb_file=@protein.pdb" \
  -F "use_celery=true"
```

**Synchronous prediction (via gateway)**:
```bash
curl -X POST https://cadd.zju.edu.cn/enzymind/api/predict/active-sites \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'
```

**Illustrative response:**
```json
{"result":"|   Residue Index | Residue Name   | Active Type   |   Confidence |\n|----------------:|:---------------|:--------------|-------------:|\n|              65 | GLY            | Binding Site  |       0.9997 |\n|              65 | GLY            | Binding Site  |       0.9996 |\n|             162 | TRP            | Binding Site  |       0.9997 |\n|             215 | ASN            | Binding Site  |       0.9999 |\n|             246 | TYR            | Binding Site  |       0.9996 |\n|             407 | ARG            | Binding Site  |       0.9999 |"}
```

---

### 8. Enzyme Type Recommendation (Port 18908)

**Recommend enzyme classes (EC numbers) from reaction SMILES.**

```bash
# Direct to service
curl -X POST http://localhost:18908/api/query/enzyme-type \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CC(=O)O>>CCO"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/enzyme-type \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CC(=O)O>>CCO"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "recommendations": [
    {"ec_number": "1.1.1.1", "confidence": 0.95},
    {"ec_number": "1.1.1.2", "confidence": 0.85}
  ],
  "formatted": ["EC 1.1.1.1 (95%)", "EC 1.1.1.2 (85%)"],
  "total_count": 2,
  "error": null
}
```

**Get Top-K recommendations**:
```bash
curl -X POST http://localhost:18908/api/query/enzyme-type/top-k \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CC(=O)O>>CCO",
    "k": 10
  }'
```

**Form input**:
```bash
curl -X POST http://localhost:18908/api/query/enzyme-type/form \
  -F "query=CC(=O)O>>CCO"
```

---

### 9. Protein Parameters (ProtParam) (Port 18909)

**Calculate protein physicochemical properties.**

The direct service endpoint on port 18909, `/api/query/protein-physchem`, exposes `parameters` directly. Both Gateway aliases, `/api/query/protein-physchem` and `/api/query/protein-params`, use the compatibility response with `data.parameters` and a readable `result`. Missing required input returns HTTP 422 through the Gateway.

```bash
# Direct to service
curl -X POST http://localhost:18909/api/query/protein-physchem \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/protein-physchem \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'
```

**Illustrative Gateway response:**
```json
{
  "result": "| Parameter | Value |\n|---|---|\n| Molecular Weight | 5892.89 Da |...",
  "data": {
    "success": true,
    "sequence_length": 52,
    "raw_text": "...",
    "parameters": {
      "molecular_weight": 5892.89,
      "theoretical_pi": 9.45,
      "instability_index": 32.5,
      "aliphatic_index": 85.2
    },
    "error": null
  }
}
```

---

### 10. Sequence Alignment / BLAST (Port 18910)

**Search protein sequences with local BLAST+ or an explicitly selected remote NCBI database.**

```bash
# Direct to service
curl -X POST http://localhost:18910/api/query/blast \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "max_results": 5
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/blast \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "max_results": 3
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "query_length": 52,
  "num_results": 3,
  "alignments": [
    {
      "title": "sp|P12345|ENZYME_HUMAN Alcohol dehydrogenase",
      "length": 375,
      "e_value": 0.0,
      "score": 900,
      "bits": 1800,
      "query": "MKFLIL--CLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
      "match": "MKFLIL  CLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
      "subject": "MKFLILLFNCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
    }
  ],
  "error": null
}
```

---

### 11. Function Query (Port 18911)

**Retrieve protein function annotations from UniProt.**

```bash
# Direct to service
curl -X POST http://localhost:18911/api/query/function \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/function \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "uniprot_id": "P12345",
  "function": "Catalyzes the reversible oxidation of ethanol to acetaldehyde...",
  "protein_name": "Alcohol dehydrogenase 1",
  "organism": "Homo sapiens",
  "gene_names": ["ADH1A", "ADH1"],
  "error": null
}
```

**Batch query**:
```bash
curl -X POST http://localhost:18911/api/query/function/batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["P12345", "Q9Y6K9", "P00352"]
  }'
```

**Illustrative response:**
```json
{
  "results": {
    "P12345": {"success": true, "function": "...", "protein_name": "..."},
    "Q9Y6K9": {"success": true, "function": "...", "protein_name": "..."},
    "P00352": {"success": true, "function": "...", "protein_name": "..."}
  },
  "total": 3,
  "successful": 3
}
```

**Upload file with UniProt IDs**:
```bash
curl -X POST http://localhost:18911/api/query/function/file \
  -F "file=@uniprot_ids.txt"
```

---

### 12. Enzyme Subclass Query (Port 18912)

**Retrieve enzyme subclass information.**

```bash
# Direct to service
curl -X POST http://localhost:18912/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Oxidoreductases",
    "num_samples": 5,
    "seed": 42
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{
    "query": "hydrolase",
    "num_samples": 10
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "enzyme_class": "Hydrolases",
  "ec_prefix": 3,
  "result": "| EC Number | Description |\n|---|---|...",
  "subclasses": [
    {
      "ID": "3.1.1.1",
      "DE": "Carboxylesterase",
      "CA": ["substrate + H2O = product"],
      "DR": ["P12345", "Q9Y6K9"]
    }
  ],
  "total_available": 500,
  "sampled": 5,
  "error": null
}
```

**Get all enzyme classes**:
```bash
curl http://localhost:18912/api/enzyme-classes
```

**Illustrative response:**
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

---

### 13. Catalytic Activity Query (Port 18913)

**Retrieve protein catalytic-activity annotations.**

```bash
# Direct to service
curl -X POST http://localhost:18913/api/query/catalytic-activity \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/catalytic-activity \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "uniprot_id": "P12345",
  "activities": [
    {
      "ec_number": "1.1.1.1",
      "reaction_name": "An alcohol + NAD+ = an aldehyde + NADH + H+"
    }
  ],
  "count": 1,
  "markdown": "| EC Number | Reaction |\n|---|---|\n| 1.1.1.1 | An alcohol + NAD+ = ... |",
  "error": null
}
```

**Batch query**:
```bash
curl -X POST http://localhost:18913/api/query/catalytic-activity/batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["P12345", "Q9Y6K9"]
  }'
```

---

### 14. Enzyme Check (Port 18914)

**Check whether UniProt annotates a protein as an enzyme.**

```bash
# Direct to service
curl -X POST http://localhost:18914/api/check/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/check/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "uniprot_id": "P12345",
  "is_enzyme": true,
  "message": "P12345 is an enzyme with EC numbers: 1.1.1.1",
  "ec_numbers": ["1.1.1.1"],
  "error": null
}
```

**Batch check**:
```bash
curl -X POST http://localhost:18914/api/check/enzyme/batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["P12345", "Q9Y6K9", "P00352"]
  }'

# Response
{
  "results": {...},
  "total": 3,
  "enzymes": 2,
  "non_enzymes": 1
}
```

---

### 15. Enzyme Full Info (Port 18915)

**Retrieve integrated enzyme information in one query.**

```bash
# Direct to service
curl -X POST http://localhost:18915/api/query/enzyme-full-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/enzyme-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "is_enzyme": true,
  "uniprot_id": "P12345",
  "sequence_info": {
    "length": 375,
    "molWeight": 39872,
    "value": "MSTAGKVIKCKAAVLWEE..."
  },
  "catalytic_activities": [
    {
      "ec": "1.1.1.1",
      "reaction": "An alcohol + NAD+ = an aldehyde + NADH + H+"
    }
  ],
  "kinetic_parameters": {
    "km": [{"value": 0.5, "unit": "mM", "substrate": "Ethanol"}],
    "vmax": [{"value": 100, "unit": "U/mg"}]
  },
  "functional_sites": [
    {"type": "ACT_SITE", "position": 45, "description": "Proton acceptor"},
    {"type": "METAL", "position": 67, "description": "Zinc; catalytic"}
  ],
  "error": null
}
```

---

### 16. Functional Site Query (Port 18916)

**Retrieve annotated functional sites.**

`start` and `end` are one-based inclusive UniProt positions. A single-residue site has equal start/end values; preserve the interval for multi-residue features.

```bash
# Direct to service
curl -X POST http://localhost:18916/api/query/features \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/features \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "uniprot_id": "P12345",
  "sites": [
    {
      "type": "Active site",
      "start": 45,
      "end": 45,
      "description": "Proton acceptor"
    },
    {
      "type": "Binding site",
      "start": 150,
      "end": 150,
      "description": "Substrate binding"
    },
    {
      "type": "Binding site",
      "start": 67,
      "end": 67,
      "description": "Zinc; catalytic"
    }
  ],
  "count": 3,
  "result": null,
  "error": null
}
```

---

### 17. Kinetic Parameters Query (Port 18917)

**Retrieve reported enzyme kinetic parameters.**

```bash
# Direct to service
curl -X POST http://localhost:18917/api/query/kinetics \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/kinetics \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "success": true,
  "uniprot_id": "P12345",
  "km": [
    {
      "substrate": "ethanol",
      "value": 0.5,
      "unit": "mM"
    }
  ],
  "vmax": [
    {
      "value": 100,
      "unit": "µmol/min/mg"
    }
  ],
  "kcat_note": "kcat values are computed from turnover numbers",
  "result": "| Parameter | Value | Unit |\n|---|---|---|...",
  "error": null
}
```

---

### 18. Sequence Info Query (Port 18918)

**Retrieve protein sequence information.**

```bash
# Direct to service
curl -X POST http://localhost:18918/api/query/sequence-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'

# Via gateway
curl -X POST https://cadd.zju.edu.cn/enzymind/api/query/sequence-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'
```

**Illustrative response:**
```json
{
  "length": 375,
  "molWeight": 39872,
  "value": "MSTAGKVIKCKAAVLWEEVKKPFSIEEVEVAPPKAHEVRIKMVATGICRSDDHVVSGTLVTPLPVIAGHEAAGIVESIGEGVTTVRPGDKVIPLFTPQCGKCRVCKHPEGNFCLKNDLSMPRGTMQDGTSRFTCRGKPIHHFLGTSTFSQYTVVDEISVAKIDAASPLEKVCLIGCGFSTGYGSAVKVAKVTQGSTCAVFGLGGVGLSVIMGCKAAGAARIIGVDINKDKFAKAKEVGATECVNPQDYKKPIQEVLTEMSNGGVDFSFEVIGRLDTMVTALSCCQEAYGVSVIVGVPPDSQNLSMNPMLLLTGRTWKGAIFGGFKSKDSVPKLVADFMAKKFALDPLITHVLPFEKINEGFDLLRSGESIRTILTF"
}
```

---

## Health Check

```bash
# Gateway health
curl https://cadd.zju.edu.cn/enzymind/api/health
```

**Illustrative response:**
```json
{"status": "healthy", "service": "api-gateway"}
```

```bash
# Individual service health checks
curl http://localhost:18901/health       # enzy_recognize
curl http://localhost:18902/health       # ecnumber_predict
curl http://localhost:18903/health       # substrate_predict
curl http://localhost:18904/health       # kcat_predict
curl http://localhost:18905/health       # km_predict
curl http://localhost:18906/health       # structure_predict
curl http://localhost:18907/health       # active_sites
curl http://localhost:18908/health       # enzyme_type
curl http://localhost:18909/health       # protparam
curl http://localhost:18910/health       # sequence_alignment
curl http://localhost:18911/health       # function_get
curl http://localhost:18912/health       # enzyme_subclass
curl http://localhost:18913/health       # ec_reaction_info
curl http://localhost:18914/health       # enzyme_check
curl http://localhost:18915/health       # enzyme_full_info
curl http://localhost:18916/health       # functional_site
curl http://localhost:18917/health       # kinetic_params
curl http://localhost:18918/health       # sequence_info
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message description",
  "detail": "Additional details if available"
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad Request (invalid input)
- `404`: Not Found (service or resource not found)
- `500`: Internal Server Error
- `503`: Service Unavailable (microservice not responding)

---

## Notes

1. **Timeout**: All proxy requests have a 300-second timeout for long-running predictions
2. **Input Types**: Most prediction endpoints support `sequence`, `fasta`, and `uniprot` input types
3. **SMILES Format**: For substrate/kinetics predictions, use valid SMILES notation (e.g., `CC(=O)O` for acetic acid)
4. **Async Operations**: Active site prediction supports async processing with job status tracking via Celery
5. **File Downloads**: PDB files are served from `/api/pdb/{filename}` after structure prediction
6. **Parameter Names**: Note the exact parameter names when making requests (case-sensitive)
7. **Gateway Mapping**: All services are accessible via the gateway under `https://cadd.zju.edu.cn/enzymind/api/`; local `/api/...` paths use this public prefix

### Compatibility routes

The current `/predict/*` and `/utility/*` pages use the canonical tool APIs.
Older clients can continue to use the following paths under `/enzymind/api`:

| Compatibility URL | Behavior |
| --- | --- |
| `POST /query/structure` | Same input, prediction and saved result as `/predict/structure`. |
| `POST /recommend/enzyme` | Same as `/query/enzyme-type`; supplying `k` uses `/query/enzyme-type/top-k` and its validation. |
| `POST /query/ec-info` | EC nomenclature, four-level classification and catalytic activity from the attributed offline ENZYME reference. Accepts `query` or `ec_number`. UniProt accessions (`query` or `uniprot_id`) retain catalytic-activity lookup behavior. |
| `GET /pdb/{filename}` | Reads a generated PDB from `STATIC_PDB_DIR` or `ESMFOLD_OUTPUT_DIR`, including `output/<job>/<job>.pdb`; the historical `/tmp` locations remain supported. Invalid paths, symlinks and oversized files are rejected. Missing/expired files still correctly return 404. |

These POST routes preserve workspace ownership and saved input/result behavior
when `X-Enzymind-Client` is supplied. For private saved structures, continue to use
`GET /workspace/results/{id}/structure` with the owning workspace key.
## Workspace Python sandbox

`POST /api/workspace/tools/python` uses the existing short-lived turn capability.
Private downloads are served at `/api/workspace/results/{result_id}/files/{file_id}`
with workspace authentication. The feature defaults off and requires a loopback
Runner, a separate service credential, and verified Rootless Docker limits.
Keep one Gateway worker and disable Uvicorn proxy-header rewriting; configure
`ENZYMIND_TRUSTED_PROXIES` explicitly for source-IP limits. See
[the sandbox deployment guide](../services/python_sandbox/README.md).
