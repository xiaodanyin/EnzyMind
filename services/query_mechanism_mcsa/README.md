# M-CSA Enzyme Query Microservice

## Enzyme records visualization

`POST /api/enzyme/query` includes the recorded compound/cofactor SMILES, the
exact reference protein's `sequence_info`, and literature references nested
under each mechanism proposal. These are read from the existing M-CSA database;
no schema migration or external annotation lookup is required. Missing or
conflicting reference sequences yield `sequence_info: null`; a homolog's
sequence is never substituted. Fine-grained queries retain their existing
optional payloads.

The shared result card in Agent and Results displays molecular depictions,
independent mechanism proposals and source step diagrams, residue roles, and
separate UniProt/PDB numbering. It reuses Ketcher, expandable figure/table
dialogs, the sequence preview and the AlphaFold reference viewer introduced
for Enzyme information. Reference structures load independently through the
existing enzyme information service; M-CSA residue identities and the entire
model numbering must match the saved sequence before site overlays are enabled.
PDB author positions are never converted to UniProt positions by offsets.

Source diagrams use only validated HTTPS URLs under the official M-CSA image
directory and render as images, never inline HTML. Failed or absent diagrams
preserve the step text and source link. Database prose is rendered as plain
text. Older saved records remain readable; rerun the M-CSA query to obtain
sequence, SMILES and literature fields absent from an older record.

Deploy with the existing `scripts/deploy.sh frontend` build stage, then restart
`query_mechanism_mcsa` with `scripts/stop.sh` / `scripts/start.sh`, and restart
the frontend with the existing Web scripts. There are no new dependencies,
Gateway changes, or changes to EasIFA services or databases.

Backend checks: `services/query_mechanism_mcsa/venv/bin/python -m unittest discover -s services/query_mechanism_mcsa/tests -v`.
Frontend checks: `npm test`, `npm run build`, and `tests/browser/mcsa-records.spec.mjs`.

A FastAPI microservice for retrieving enzyme catalytic mechanisms by M-CSA ID, UniProt accession or PDB ID.

## API design

**Query endpoints use POST with JSON bodies**, making them suitable for language-model tool calls. Health and documentation endpoints retain their normal HTTP methods.

---

## Project layout

```
services/query_mechanism_mcsa/
├── db/
│   └── mcsa.db           # SQLite database
├── models.py             # SQLAlchemy ORM models
├── retriever.py          # Data retrieval
├── main.py               # FastAPI application
├── requirements.txt      # Dependencies
└── README.md             # Documentation
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Import data

Import M-CSA JSON into SQLite with the data conversion script:

```bash
cd script
python transfer_mcsa_to_db.py
```

## Start the service

```bash
cd services/query_mechanism_mcsa
uvicorn main:app --reload --host 0.0.0.0 --port 18919
```

## API documentation

After starting the service, open its interactive API documentation:
- Swagger UI: http://localhost:18919/docs
- ReDoc: http://localhost:18919/redoc

---

## API overview

| Endpoint | Purpose | Request parameters |
|------|------|----------|
| `POST /api/enzyme/query` | Retrieve complete enzyme information | `{"query_id": "..."}` |
| `POST /api/enzyme/reaction` | Retrieve reaction information | `{"query_id": "..."}` |
| `POST /api/enzyme/active_sites` | Retrieve catalytic residues | `{"query_id": "...", "view": "both"}` |
| `POST /api/enzyme/mechanism/summary` | Retrieve the mechanism summary | `{"query_id": "..."}` |
| `POST /api/enzyme/mechanism/steps` | Retrieve detailed mechanism steps | `{"query_id": "..."}` |
| `POST /api/enzyme/mechanism/electron_flows` | Retrieve electron flow information | `{"query_id": "...", "include_cxsmiles": false}` |
| `POST /api/enzyme/mechanism/electron_flows/summary` | Retrieve the electron flow summary | `{"query_id": "..."}` |
| `POST /api/enzyme/cofactors` | Retrieve cofactor information | `{"query_id": "..."}` |
| `POST /api/enzyme/search` | Search enzymes by name | `{"name": "...", "limit": 10}` |
| `POST /api/enzyme/list` | List enzymes with pagination | `{"page": 1, "per_page": 50}` |
| `POST /api/enzyme/identifiers` | Retrieve all identifiers | `{"query_id": "..."}` |

---

## API usage

### Supported identifiers

| Type | Examples | Description |
|------|------|------|
| MCSA ID | `"1"`, `"M1"`, `"MCSA:1"` | Numeric or prefixed ID |
| UniProt ID | `"P56868"`, `"P62593"` | Standard UniProt accession |
| PDB ID | `"1b73"`, `"2FQX"` | Four-character PDB code |

---

### 1. Retrieve complete enzyme information

**Endpoint:** `POST /api/enzyme/query`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/query \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response:** includes `basic_info`, `active_sites_uniprot`, `active_sites_pdb`, `reaction` and `mechanism`.

---

### 2. Retrieve reaction information

**Endpoint:** `POST /api/enzyme/reaction`

**Request:**
```json
{
    "query_id": "P56868",
    "include_smiles": true
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/reaction \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Example response:**
```json
{
    "query_id": "P56868",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "reaction": {
        "ec": "5.1.1.3",
        "is_polymeric": false,
        "reactants": [
            {"name": "L-glutamate(1-)", "count": 1, "chebi_id": "29985"}
        ],
        "products": [
            {"name": "D-glutamate(1-)", "count": 1, "chebi_id": "29986"}
        ]
    }
}
```

---

### 3. Retrieve catalytic residues

**Endpoint:** `POST /api/enzyme/active_sites`

**Request parameters:**
- `query_id` (required): Enzyme identifier
- `view` (optional): Choose a residue-numbering view:
  - `"uniprot"`: UniProt sequence positions only
  - `"pdb"`: PDB structure positions only
  - `"both"`: Both views (default)

**Example request: UniProt view only:**
```json
{
    "query_id": "P56868",
    "view": "uniprot"
}
```

**Example request: PDB view only:**
```json
{
    "query_id": "P56868",
    "view": "pdb"
}
```

**Example request: both views:**
```json
{
    "query_id": "P56868",
    "view": "both"
}

```
**Example request: both views with the amino acid sequence:**
```json
{
    "query_id": "P56868",
    "view": "both",
    "include_sequence": true
}
```

**curl example:**
```bash
# UniProt numbering
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "uniprot"}'

# PDB numbering
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "pdb"}'

# Both numbering views
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "both"}'
```

**Example response (UniProt view):**
```json
{
    "query_id": "P56868",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "view": "uniprot",
    "active_sites_uniprot": [
        {
            "uniprot_id": "P56868",
            "code": "Asp",
            "resid": 7,
            "is_reference": true,
            "roles": ["activator", "proton acceptor", "hydrogen bond acceptor"],
            "roles_summary": "activator, electrostatic stabiliser, hydrogen bond acceptor, hydrogen bond donor, proton acceptor"
        },
        {
            "uniprot_id": "P56868",
            "code": "Cys",
            "resid": 70,
            "is_reference": true,
            "roles": ["proton donor", "proton acceptor"],
            "roles_summary": "activator, proton acceptor, proton donor"
        }
    ],
    "active_sites_pdb": null
}
```

**Example response (PDB view):**
```json
{
    "query_id": "P56868",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "view": "pdb",
    "active_sites_uniprot": null,
    "active_sites_pdb": [
        {
            "pdb_id": "1b73",
            "chain": "A",
            "code": "Asp",
            "resid": 7,
            "auth_resid": 7,
            "is_reference": true,
            "domain_name": "A01",
            "domain_cath_id": "3.40.50.1860",
            "roles": ["activator", "proton acceptor"],
            "roles_summary": "activator, electrostatic stabiliser, hydrogen bond acceptor, hydrogen bond donor, proton acceptor"
        }
    ]
}
```

---

### 4. Retrieve the catalytic mechanism summary

**Endpoint:** `POST /api/enzyme/mechanism/summary`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/mechanism/summary \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Example response:**
```json
{
    "query_id": "P56868",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "summary_text": "A two base mechanism is proposed where Cys70 and Cys178 are responsible for the deprotonation and protonation of the C-alpha atom of D-Glutamate, respectively. Cys70 deprotonates the C-alpha to form an enolate intermediate before Cys178 reprotonates on the opposite face to produce L-Glutamate. The carboxylates of Asp7 and Glu147 are also important in catalysis by assisting activation of the acid/base thiols.",
    "components_summary": "intermediate formation, assisted keto-enol tautomerisation, proton transfer, atom stereo change, native state of enzyme regenerated",
    "is_detailed": true,
    "rating": 3
}
```

---

### 5. Retrieve detailed catalytic mechanism steps

**Endpoint:** `POST /api/enzyme/mechanism/steps`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/mechanism/steps \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Example response:**
```json
{
    "query_id": "P56868",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "summary_text": "A two base mechanism is proposed where Cys70 and Cys178 are responsible for the deprotonation and protonation of the C-alpha atom of D-Glutamate...",
    "steps": [
        {
            "step_id": 1,
            "description": "Asp7 deprotonates Cys70, activating it.",
            "is_product": false,
            "figure": "www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_1_1"
        },
        {
            "step_id": 2,
            "description": "Cys70 deprotonates the L-glutamate substrate, initiating a double bond rearrangement and forming the planar enolate.",
            "is_product": false,
            "figure": "www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_mechanism_1_step_2_4fKdyFt"
        },
        {
            "step_id": 3,
            "description": "The enolate collapses, resulting in the deprotonation of Cys178, which is on the opposite side of Cys70. This forms the opposite isomer.",
            "is_product": false,
            "figure": "www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_mechanism_1_step_3_ofPtCeJ"
        },
        {
            "step_id": 4,
            "description": "Cys178 deprotonates Glu147B, activating the enzyme for the return reaction.",
            "is_product": false,
            "figure": "www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_mechanism_1_step_4_X4F7jnc"
        },
        {
            "step_id": 5,
            "description": "Products",
            "is_product": true,
            "figure": "www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_mechanism_1_step_5_jriKXKD"
        }
    ]
}
```

---

### 6. Retrieve electron flow information

**Endpoint:** `POST /api/enzyme/mechanism/electron_flows`

Retrieve how electrons move between atoms in each mechanism step.

**Request parameters:**
- `query_id` (required): Enzyme identifier
- `mechanism_id` (optional): Select one mechanism when multiple proposals exist
- `step_index` (optional): Select a step (0 = reactants, 1 = step 1, 2 = step 2, and so on)
- `include_cxsmiles` (optional): Include CXSMILES molecular representations; default `false` to reduce response size

**Example request: compact response:**
```json
{
    "query_id": "P56868"
}
```

**Example request: full details:**
```json
{
    "query_id": "P56868",
    "mechanism_id": 1,
    "step_index": 1,
    "include_cxsmiles": true
}
```

**curl example:**
```bash
# Compact query: omit CXSMILES by default
curl -X POST http://localhost:18919/api/enzyme/mechanism/electron_flows \
  -H "Content-Type: application/json" \
  -d '{"query_id": "1"}'

# Retrieve full details for a selected step
curl -X POST http://localhost:18919/api/enzyme/mechanism/electron_flows \
  -H "Content-Type: application/json" \
  -d '{"query_id": "1", "step_index": 1, "include_cxsmiles": true}'
```

**Example response excerpt (`include_cxsmiles=false`; optional localized descriptions omitted):**
```json
{
    "found": true,
    "message": "Successfully retrieved electron flow information for enzyme 'glutamate racemase': 6 steps, 4 with electron flow data.",
    "query_id": "1",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "total_steps": 6,
    "steps": [
        {
            "step_index": 0,
            "role": "reactant",
            "description": null,
            "mechanism_id": 1,
            "electron_flows": [],
            "involved_residues": [],
            "alignment_match_rate": null,
            "alignment_warnings": null
        },
        {
            "step_index": 1,
            "role": "intermediate",
            "description": "Asp7 deprotonates Cys70, activating it.",
            "mechanism_id": 1,
            "electron_flows": [
                {
                    "index": 1,
                    "electron_count": 2,
                    "arrow_type": "electron_pair",

                    "source": {
                        "type": "bond",
                        "atom1_index": 8,
                        "atom2_index": 3,
                        "atom1_element": "S",
                        "atom2_element": "H",
                        "bond_order": 1,
                        "mrv_atom1_index": 18,
                        "mrv_atom2_index": 37
                    },
                    "target": {
                        "type": "atom",
                        "index": 8,
                        "element": "S",
                        "formal_charge": 0,

                        "mrv_index": 18
                    }
                },
                {
                    "index": 2,
                    "electron_count": 2,
                    "arrow_type": "electron_pair",

                    "source": {
                        "type": "atom",
                        "index": 14,
                        "element": "O",
                        "formal_charge": -1,

                        "mrv_index": 25
                    },
                    "target": {
                        "type": "atom_pair",
                        "atom1": {"type": "atom", "index": 14, "element": "O", "mrv_index": 25},
                        "atom2": {"type": "atom", "index": 3, "element": "H", "mrv_index": 37}

                    }
                }
            ],
            "involved_residues": ["Cys70A", "Asp7A"],
            "alignment_match_rate": 1.0,
            "alignment_warnings": null
        }
    ]
}
```

**Additional fields when `include_cxsmiles=true`:**
```json
{
    "steps": [
        {
            "step_index": 1,
            "cxsmiles": "[H]OC(=O)C([H])([H])C([H])([H])...",
            "electron_flows": [
                {
                    "source": {
                        "type": "bond",
                        "cxsmiles_atom1_index": 8,
                        "cxsmiles_atom2_index": 3,
                        "description_cxsmiles": "S(8)-H(3) bond"
                    },
                    "target": {
                        "cxsmiles_index": 8,
                        "description_cxsmiles": "S(CXSMILES idx 8)"
                    }
                }
            ]
        }
    ]
}
```

---

### 7. Retrieve the electron flow summary

**Endpoint:** `POST /api/enzyme/mechanism/electron_flows/summary`

Retrieve a mechanism overview with step counts and participating catalytic residues.

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/mechanism/electron_flows/summary \
  -H "Content-Type: application/json" \
  -d '{"query_id": "1"}'
```

**Example response:**
```json
{
    "found": true,
    "message": "Successfully retrieved electron flow summary for enzyme 'glutamate racemase': 1 mechanism(s) with 6 total steps, involving 4 catalytic residues.",
    "query_id": "1",
    "enzyme_name": "glutamate racemase",
    "mcsa_id": 1,
    "mechanism_count": 1,
    "all_involved_residues": ["Asp7A", "Cys178A", "Cys70A", "Glu147A-2"],
    "mechanisms": [
        {
            "mechanism_id": 1,
            "step_count": 6,
            "steps_with_electron_flows": 4,
            "involved_residues": ["Asp7A", "Cys178A", "Cys70A", "Glu147A-2"]
        }
    ]
}
```

---

### 8. Retrieve cofactor information

**Endpoint:** `POST /api/enzyme/cofactors`

Cofactors are non-protein participants in enzyme catalysis, including FAD, NAD and metal ions such as Cu or Zn.

**Request:**
```json
{
    "query_id": "P56868",
    "include_smiles": true
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/cofactors \
  -H "Content-Type: application/json" \
  -d '{"query_id": "3"}'
```

**Example response:**
```json
{
    "found": true,
    "message": "Successfully retrieved cofactor information for enzyme 'NAD(P)H dehydrogenase (quinone)': 2 cofactor(s) found (PLQ, FAD).",
    "query_id": "3",
    "enzyme_name": "NAD(P)H dehydrogenase (quinone)",
    "mcsa_id": 3,
    "cofactors": [
        {
            "pdb_code": "PLQ",
            "name": "1,4-benzoquinone",
            "chebi_id": "16509",
            "kegg_compound": "C15602",
            "uniprot_id": "P15559",
            "pdb_id": "1d4a",
            "ec": "1.6.5.2",
            "roles": [
                {"role": "activator", "role_type": "spectator", "role_group": "activator"},
                {"role": "hydride acceptor", "role_type": "reactant", "role_group": "hydride shuttle"},
                {"role": "proton acceptor", "role_type": "reactant", "role_group": "proton shuttle (general acid/base)"}
            ]
        },
        {
            "pdb_code": "FAD",
            "name": "FADH2(2-)",
            "chebi_id": "58307",
            "kegg_compound": null,
            "uniprot_id": "P15559",
            "pdb_id": "1d4a",
            "ec": "1.6.5.2",
            "roles": [
                {"role": "hydride acceptor", "role_type": "reactant", "role_group": "hydride shuttle"},
                {"role": "hydride donor", "role_type": "reactant", "role_group": "hydride shuttle"},
                {"role": "proton acceptor", "role_type": "reactant", "role_group": "proton shuttle (general acid/base)"},
                {"role": "proton donor", "role_type": "reactant", "role_group": "proton shuttle (general acid/base)"}
            ]
        }
    ]
}
```

---

### 9. Search enzymes by name

**Endpoint:** `POST /api/enzyme/search`

**Request parameters:**
- `name` (required): Enzyme name, with partial matching
- `limit` (optional): Maximum results; default 10, range 1–100

**Request:**
```json
{
    "name": "lactamase",
    "limit": 5
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/search \
  -H "Content-Type: application/json" \
  -d '{"name": "lactamase", "limit": 5}'
```

**Example response:**
```json
[
    {"mcsa_id": 2, "enzyme_name": "beta-lactamase (Class A)", "reference_uniprot_id": "P62593"},
    {"mcsa_id": 15, "enzyme_name": "beta-lactamase (Class B1)", "reference_uniprot_id": "P25910"},
    {"mcsa_id": 16, "enzyme_name": "beta-lactamase (Class B1)", "reference_uniprot_id": "P04190"},
    {"mcsa_id": 210, "enzyme_name": "beta-lactamase (Class D)", "reference_uniprot_id": "P13661"},
    {"mcsa_id": 257, "enzyme_name": "beta-lactamase (Class C)", "reference_uniprot_id": "P05364"}
]
```

---

### 10. List enzymes with pagination

**Endpoint:** `POST /api/enzyme/list`

**Request parameters:**
- `page` (optional): Page number; default 1
- `per_page` (optional): Records per page; default 50, range 1–100

**Request:**
```json
{
    "page": 1,
    "per_page": 10
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/list \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "per_page": 10}'
```

**Example response:**
```json
{
    "total": 1003,
    "page": 1,
    "per_page": 10,
    "total_pages": 101,
    "results": [
        {"mcsa_id": 1, "enzyme_name": "glutamate racemase", "reference_uniprot_id": "P56868"},
        {"mcsa_id": 2, "enzyme_name": "beta-lactamase (Class A)", "reference_uniprot_id": "P62593"}
    ]
}
```

---

### 11. Retrieve all enzyme identifiers

**Endpoint:** `POST /api/enzyme/identifiers`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/identifiers \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Example response:**
```json
{
    "query_id": "P56868",
    "mcsa_id": 1,
    "identifiers": {
        "mcsa": ["1"],
        "uniprot": ["P56868"],
        "pdb": ["1b73"]
    }
}
```

---

## Python examples

### Client class

```python
import requests
from typing import Optional, Dict, List, Any


class MCSAClient:
    """M-CSA client suitable for language-model tool calls."""
    
    def __init__(self, base_url: str = "http://localhost:18919"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
    
    def _post(self, endpoint: str, data: dict) -> dict:
        """Send a POST request."""
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # ========== Complete record queries ==========
    
    def query(self, query_id: str) -> dict:
        """
        Retrieve complete enzyme information
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/query", {"query_id": query_id})
    
    # ========== Reaction queries ==========
    
    def get_reaction(self, query_id: str) -> dict:
        """
        Retrieve reaction information (reactants and products)
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/reaction", {"query_id": query_id})
    
    # ========== Catalytic residue queries ==========
    
    def get_active_sites(
        self, 
        query_id: str, 
        view: str = "both"
    ) -> dict:
        """
        Retrieve catalytic residues
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
            view: Numbering view: "uniprot", "pdb", or "both"
        """
        return self._post("/api/enzyme/active_sites", {
            "query_id": query_id,
            "view": view
        })
    
    # ========== Mechanism queries ==========
    
    def get_mechanism_summary(self, query_id: str) -> dict:
        """
        Retrieve the catalytic mechanism summary
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/mechanism/summary", {"query_id": query_id})
    
    def get_mechanism_steps(self, query_id: str) -> dict:
        """
        Retrieve detailed catalytic mechanism steps
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/mechanism/steps", {"query_id": query_id})
    
    # ========== Cofactor queries ==========
    
    def get_cofactors(self, query_id: str) -> dict:
        """
        Retrieve cofactor information
        
        Cofactors are non-protein catalytic participants, including FAD, NAD and metal ions.
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/cofactors", {"query_id": query_id})
    
    # ========== Search and listing ==========
    
    def search(self, name: str, limit: int = 10) -> list:
        """
        Search enzymes by name
        
        Args:
            name: Enzyme name, with partial matching
            limit: Maximum results
        """
        return self._post("/api/enzyme/search", {"name": name, "limit": limit})
    
    def list_enzymes(self, page: int = 1, per_page: int = 50) -> dict:
        """
        List enzymes with pagination
        
        Args:
            page: Page number
            per_page: Records per page
        """
        return self._post("/api/enzyme/list", {"page": page, "per_page": per_page})
    
    # ========== Identifier queries ==========
    
    def get_identifiers(self, query_id: str) -> dict:
        """
        Retrieve all enzyme identifiers
        
        Args:
            query_id: M-CSA ID, UniProt accession, or PDB ID
        """
        return self._post("/api/enzyme/identifiers", {"query_id": query_id})


# ========== Examples ==========

if __name__ == "__main__":
    client = MCSAClient()
    
    # 1. Query the reaction
    reaction = client.get_reaction("P56868")
    print("=== Reaction information ===")
    print(f"Enzyme name: {reaction['enzyme_name']}")
    print(f"EC number: {reaction['reaction']['ec']}")
    print(f"Reactants: {[r['name'] for r in reaction['reaction']['reactants']]}")
    print(f"Products: {[p['name'] for p in reaction['reaction']['products']]}")
    
    # 2. Retrieve catalytic residues (UniProt numbering)
    sites = client.get_active_sites("P56868", view="uniprot")
    print("\n=== Catalytic residues (UniProt) ===")
    for site in sites["active_sites_uniprot"]:
        print(f"  {site['code']}{site['resid']}: {', '.join(site['roles'])}")
    
    # 3. Retrieve the mechanism summary
    summary = client.get_mechanism_summary("P56868")
    print("\n=== Mechanism summary ===")
    print(summary["summary_text"])
    
    # 4. Retrieve mechanism steps
    steps = client.get_mechanism_steps("P56868")
    print("\n=== Mechanism steps ===")
    for step in steps["steps"]:
        print(f"Step {step['step_id']}: {step['description']}")
    
    # 5. Retrieve cofactors
    cofactors = client.get_cofactors("3")
    print("\n=== Cofactor information ===")
    print(f"Enzyme name: {cofactors['enzyme_name']}")
    for cof in cofactors["cofactors"]:
        print(f"  {cof['pdb_code']} ({cof['name']}): {', '.join([r['role'] for r in cof['roles']])}")
```

---

## Language-model tool integration

### Function-calling definitions

```json
{
    "name": "query_enzyme_reaction",
    "description": "Retrieve enzyme reaction information, including reactants and products",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier: M-CSA ID, UniProt accession or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_active_sites",
    "description": "Retrieve enzyme catalytic residues",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier: M-CSA ID, UniProt accession or PDB ID"
            },
            "view": {
                "type": "string",
                "enum": ["uniprot", "pdb", "both"],
                "description": "Numbering view: uniprot (sequence positions), pdb (structure positions), or both"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_mechanism_summary",
    "description": "Retrieve a summary of the enzyme mechanism",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier: M-CSA ID, UniProt accession or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_mechanism_steps",
    "description": "Retrieve detailed steps in the enzyme mechanism",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier: M-CSA ID, UniProt accession or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_cofactors",
    "description": "Retrieve enzyme cofactors, including FAD, NAD, metal ions and other non-protein catalytic participants",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier: M-CSA ID, UniProt accession or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

---

## Response field reference

### Reaction fields

| Field | Type | Description |
|------|------|------|
| `reaction.ec` | string | EC classification |
| `reaction.is_polymeric` | bool | Whether the reaction involves a polymer |
| `reaction.reactants` | list | Reactants |
| `reaction.reactants[].name` | string | Compound name |
| `reaction.reactants[].chebi_id` | string | ChEBI ID |
| `reaction.products` | list | Products |

### Catalytic residue fields

| Field | Type | Description |
|------|------|------|
| `active_sites_uniprot[].code` | string | Three-letter amino acid code |
| `active_sites_uniprot[].resid` | int | Position in the UniProt sequence |
| `active_sites_uniprot[].roles` | list | Functional roles |
| `active_sites_pdb[].pdb_id` | string | PDB ID |
| `active_sites_pdb[].chain` | string | Chain identifier |
| `active_sites_pdb[].resid` | int | Recorded PDB residue index; do not infer a UniProt offset |
| `active_sites_pdb[].auth_resid` | int/null | PDB author residue number |
| `active_sites_pdb[].code` | string | Recorded amino acid code |

### Mechanism fields

| Field | Type | Description |
|------|------|------|
| `summary_text` | string | Mechanism summary text |
| `components_summary` | string | Mechanism component summary |
| `is_detailed` | bool | Whether a detailed mechanism is available |
| `rating` | int | Reported mechanism rating |
| `steps[].step_id` | int | Step identifier |
| `steps[].description` | string | Step description |
| `steps[].is_product` | bool | Whether this is the final product step |

### Electron flow fields

| Field | Type | Description |
|------|------|------|
| `total_steps` | int | Total steps |
| `steps[].step_index` | int | Step index (0 = reactants) |
| `steps[].role` | string | Step role: reactant/intermediate/product |
| `steps[].electron_flows` | list | Electron flows |
| `steps[].electron_flows[].index` | int | Electron flow index |
| `steps[].electron_flows[].electron_count` | int | Electrons transferred (1 = single electron, 2 = electron pair) |
| `steps[].electron_flows[].arrow_type` | string | Arrow type: electron_pair/single_electron |
| `steps[].electron_flows[].source` | object | Electron source (atom/bond/lone pair) |
| `steps[].electron_flows[].target` | object | Electron target (atom/atom pair) |
| `steps[].involved_residues` | list | Catalytic residues involved in the step |
| `steps[].cxsmiles` | string | CXSMILES representation (requires include_cxsmiles=true) |
| `steps[].alignment_match_rate` | float | Atom-alignment quality score (0–1) |

### Cofactor fields

| Field | Type | Description |
|------|------|------|
| `cofactors[].pdb_code` | string | Cofactor code, such as FAD, NAD or CU |
| `cofactors[].name` | string | Cofactor name |
| `cofactors[].chebi_id` | string | ChEBI identifier |
| `cofactors[].kegg_compound` | string | KEGG compound ID |
| `cofactors[].uniprot_id` | string | Associated UniProt accession |
| `cofactors[].pdb_id` | string | Associated PDB ID |
| `cofactors[].ec` | string | EC classification |
| `cofactors[].roles` | list | Functional roles |
| `cofactors[].roles[].role` | string | Role name, such as hydride donor |
| `cofactors[].roles[].role_type` | string | Role type: reactant, spectator or interaction |
| `cofactors[].roles[].role_group` | string | Role group, such as hydride shuttle |

---

## Technology stack

- Python 3.10+
- FastAPI
- SQLAlchemy (ORM 2.0)
- SQLite
- Pydantic
- Uvicorn
