# EnzyMind API Gateway

API Gateway server for routing frontend requests to EnzyMind microservices.

## Overview

This is a lightweight FastAPI server that:
- Proxies API requests to appropriate microservices (ports 18901-18918)
- Handles CORS for Vue frontend
- Serves PDB files from structure prediction outputs
- Provides unified API endpoints with `/api` and `/enzymind/api` prefixes

## Installation

```bash
cd gateway
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
# Development
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENZYMIND_HOST` | `localhost` | Host where microservices run |

---

## API Endpoints Reference

### Service Port Mapping

| Port | Service Name | Description |
|------|--------------|-------------|
| 18901 | enzy_recognize | Enzyme recognition |
| 18902 | ecnumber_predict | EC number prediction |
| 18903 | substrate_predict | Substrate determination |
| 18904 | kcat_predict | Kcat prediction |
| 18905 | km_predict | Km prediction |
| 18906 | structure_predict | Protein structure prediction (ESMFold) |
| 18907 | active_sites | Active site prediction (EasIFA) |
| 18908 | enzyme_type | Enzyme type recommendation |
| 18909 | protparam | Protein physicochemical properties analysis |
| 18910 | sequence_alignment | BLAST sequence alignment |
| 18911 | function_get | Protein function query |
| 18912 | enzyme_subclass | Enzyme subclass query |
| 18913 | ec_reaction_info | Catalytic activity query |
| 18914 | enzyme_check | Enzyme check (UniProt lookup) |
| 18915 | enzyme_full_info | Enzyme full info query |
| 18916 | functional_site | Functional site query |
| 18917 | kinetic_params | Kinetic parameters query |
| 18918 | sequence_info | Sequence information query |

---

## Complete API Usage Examples

### 1. Enzyme Recognition (Port 18901)

**Determine whether an amino-acid sequence corresponds to an enzyme, and return a confidence score.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST http://localhost:8080/api/recognize/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "result": {
    "is_enzyme": true,
    "confidence": 0.9542
  }
```

---

### 2. EC Number Prediction (Port 18902)

**Predict the Enzyme Commission (EC) number for an amino-acid sequence, and return the predicted EC label.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "uniprot",
    "query": "P12345"
  }'

curl -X POST http://localhost:8080/api/predict/ec \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "sequence",
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "result": {
    "ec_number": "3.4.21.4"
  }
```

---

### 3. Substrate Determination (Port 18903)

**Determine whether a given enzyme can catalyze a specific substrate molecule, and return a confidence score.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'

curl -X POST http://localhost:8080/api/predict/substrate \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "sequence",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "result": {
    "is_substrate": true,
    "confidence": 0.8765
  }
```

---

### 4. Kcat Prediction (Port 18904)

**Predict the turnover number (kcat) for an enzyme–substrate pair, and return the estimated kcat value.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'

curl -X POST http://localhost:8080/api/predict/kcat \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "success": true,
  "kcat": 12.3456,
  "unit": "s^-1",
  "error": null
}
```

---

### 5. Km Prediction (Port 18905)

**Predict the Michaelis constant (Km) for an enzyme–substrate pair, and return the estimated Km value.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_input_type": "uniprot",
    "enzyme_query": "P12345"
  }'

curl -X POST http://localhost:8080/api/predict/km \
  -H "Content-Type: application/json" \
  -d '{
    "smiles": "CC(=O)O",
    "enzyme_query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "success": true,
  "km": 0.5432,
  "unit": "mM",
  "error": null
}
```

---

### 6. Structure Prediction (Port 18906)

**Predicts a protein 3D structure from a UniProt ID or amino-acid sequence, and returns the generated PDB file path (and a static URL) together with the resolved sequence and its length.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "input_type": "sequence",
    "output_name": "my_protein"
  }'

curl -X POST http://localhost:8080/api/predict/structure \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "input_type": "uniprot"
  }'

# Response
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
curl -X POST http://localhost:8080/api/predict/structure/download \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "input_type": "uniprot"
  }' -o protein.pdb
```
---

### 7. Active Sites Prediction (Port 18907)

**Predict catalytic active-site residues for a protein sequence, and return the residue identities and their positions.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/predict/active-sites \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'

curl -X POST https://enzymindactions.iddd.group/api/predict/active-sites \
  -H "Content-Type: application/json" \
  -d '{"aa_sequence": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'

# Response
{"result":"|   Residue Index | Residue Name   | Active Type   |   Confidence |\n|----------------:|:---------------|:--------------|-------------:|\n|              65 | GLY            | Binding Site  |       0.9997 |\n|              65 | GLY            | Binding Site  |       0.9996 |\n|             162 | TRP            | Binding Site  |       0.9997 |\n|             215 | ASN            | Binding Site  |       0.9999 |\n|             246 | TYR            | Binding Site  |       0.9996 |\n|             407 | ARG            | Binding Site  |       0.9999 |"}
```

---

### 8. Enzyme Type Recommendation (Port 18908)

**Recommend suitable enzyme types (e.g., EC classes) for a given chemical reaction.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/enzyme-type \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CC(=O)O>>CCO"
  }'

# Response
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

---

### 9. Protein Parameters (ProtParam) (Port 18909)

**Computes basic physicochemical properties for a protein sequence, and returns metrics.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/protein-params \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
  }'

# Response
{
  "success": true,
  "sequence_length": 52,
  "markdown": "| Parameter | Value |\n|---|---|\n| Molecular Weight | 5892.89 Da |...",
  "raw_text": "...",
  "parameters": {
    "molecular_weight": 5892.89,
    "theoretical_pi": 9.45,
    "instability_index": 32.5,
    "aliphatic_index": 85.2
  },
  "error": null
```

---

### 10. Sequence Alignment / BLAST (Port 18910)

**Performs an NCBI BLAST sequence similarity search for a given protein sequence, and returns the top hits with alignment details and statistics.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/blast \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345",
    "max_results": 3
  }'

# Response
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

**Retrieve the functional annotation of a UniProt protein entry, and returns a concise function description together with basic metadata.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/function \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Response
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

---

### 12. Enzyme Subclass Query (Port 18912)

**Retrieves EC subclasses under a specified enzyme class (e.g., Hydrolases/Oxidoreductases).**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/enzyme-subclass \
  -H "Content-Type: application/json" \
  -d '{
    "query": "hydrolase",
    "num_samples": 10
  }'

# Response
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

---

### 13. Catalytic Activity Query (Port 18913)

**Retrieve the catalytic activity of an enzyme, and return its annotated EC number(s) together with the corresponding reaction equation(s).**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/catalytic-activity \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Response
{
  "success": true,
  "uniprot_id": "P12345",
  "activities": [
    {
      "ec": "1.1.1.1",
      "reaction": "An alcohol + NAD+ = an aldehyde + NADH + H+"
    }
  ],
  "count": 1,
  "markdown": "| EC Number | Reaction |\n|---|---|\n| 1.1.1.1 | An alcohol + NAD+ = ... |",
  "error": null
}
```

---

### 14. Enzyme Check (Port 18914)

**Check whether a protein (UniProt ID) is annotated as an enzyme, and return the enzyme status.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/check/enzyme \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Response
{
  "success": true,
  "uniprot_id": "P12345",
  "is_enzyme": true,
  "message": "P12345 is an enzyme with EC numbers: 1.1.1.1",
  "ec_numbers": ["1.1.1.1"],
  "error": null
}
```

---

### 15. Enzyme Full Info (Port 18915)

**One-stop query that determines whether a UniProt entry is an enzyme and returns an integrated summary.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/enzyme-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'

# Response
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

**Retrieve active site annotations for an enzyme, and return the key residues and their positions with site types.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/features \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Response
{
  "success": true,
  "uniprot_id": "P12345",
  "sites": [
    {
      "type": "ACT_SITE",
      "position": 45,
      "description": "Proton acceptor"
    },
    {
      "type": "BINDING",
      "position": 150,
      "description": "Substrate binding"
    },
    {
      "type": "METAL",
      "position": 67,
      "description": "Zinc; catalytic"
    }
  ],
  "count": 3,
  "result": "| Type | Position | Description |\n|---|---|---|...",
  "error": null
}
```

---

### 17. Kinetic Parameters Query (Port 18917)

**Retrieve enzyme kinetic parameters, and return available values along with the associated substrates, experimental conditions.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/kinetics \
  -H "Content-Type: application/json" \
  -d '{
    "query": "P12345"
  }'

# Response
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

**Retrieve basic information for a protein sequence (UniProt ID), and return the full sequence string along with its length and molecular weight.**

```bash
# Via gateway
curl -X POST http://localhost:8080/api/query/sequence-info \
  -H "Content-Type: application/json" \
  -d '{
    "uniprot_id": "P12345"
  }'

# Response
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
curl http://localhost:8080/health
# or
curl http://localhost:8080/api/health

# Response
"status": "healthy", "service": "api-gateway"}

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
7. **Gateway Mapping**: All services are accessible via the gateway at `http://localhost:8080` with the same endpoint paths
