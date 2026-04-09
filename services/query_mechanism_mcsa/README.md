# M-CSA Enzyme Query Microservice

Based on FastAPI, an enzyme catalytic mechanism query microservice that supports retrieval of detailed enzyme information through MCSA ID, UniProt ID or PDB ID.

## 🎯 Design Principles

**All API endpoints use POST method, passing parameters through JSON body**, which facilitates integration with Large Language Models' Function Call feature.

---

## Project Structure

```
services/query_mechanism_mcsa/
├── db/
│   └── mcsa.db           # SQLite database file
├── models.py             # SQLAlchemy ORM models
├── retriever.py          # Data retrieval class
├── main.py               # FastAPI application entry point
├── requirements.txt      # Dependencies
└── README.md             # Documentation
```

## Install Dependencies

```bash
cd services/query_mechanism_mcsa
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Start Service

```bash
cd services/query_mechanism_mcsa
uvicorn main:app --reload --host 0.0.0.0 --port 18919
```

## API Documentation

After starting the service, visit the following addresses to view interactive API documentation:
- Swagger UI: http://localhost:18919/docs
- ReDoc: http://localhost:18919/redoc

---

## 📋 API Endpoints Overview

| Endpoint | Function | Request Parameters |
|------|------|----------|
| `POST /api/enzyme/query` | Query complete enzyme information | `{"query_id": "..."}` |
| `POST /api/enzyme/reaction` | Query reaction information | `{"query_id": "..."}` |
| `POST /api/enzyme/active_sites` | Query active sites | `{"query_id": "...", "view": "both"}` |
| `POST /api/enzyme/mechanism/summary` | Query mechanism summary | `{"query_id": "..."}` |
| `POST /api/enzyme/mechanism/steps` | Query detailed mechanism steps | `{"query_id": "..."}` |
| `POST /api/enzyme/search` | Search enzymes by name | `{"name": "...", "limit": 10}` |
| `POST /api/enzyme/list` | Paginate through all enzymes | `{"page": 1, "per_page": 50}` |
| `POST /api/enzyme/identifiers` | Get all identifiers | `{"query_id": "..."}` |

---

## 🔧 Detailed API Usage Guide

### Supported Identifier Formats

| Type | Example | Description |
|------|------|------|
| MCSA ID | `"1"`, `"M1"`, `"MCSA:1"` | Numeric or prefixed |
| UniProt ID | `"P56868"`, `"P62593"` | Standard UniProt format |
| PDB ID | `"1b73"`, `"2FQX"` | 4-character PDB code |

---

### 1. Query Complete Enzyme Information

**Endpoint:** `POST /api/enzyme/query`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/query \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response:** Contains `basic_info`, `active_sites_uniprot`, `active_sites_pdb`, `reaction`, `mechanism` complete information.

---

### 2. Query Reaction Information

**Endpoint:** `POST /api/enzyme/reaction`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/reaction \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response Example:**
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

### 3. Query Active Sites

**Endpoint:** `POST /api/enzyme/active_sites`

**Request Parameters:**
- `query_id` (required): Enzyme identifier
- `view` (optional): Viewpoint, options:
  - `"uniprot"`: Return only UniProt perspective
  - `"pdb"`: Return only PDB perspective
  - `"both"`: Return both perspectives (default)

**Request Example - UniProt Perspective Only:**
```json
{
    "query_id": "P56868",
    "view": "uniprot"
}
```

**Request Example - PDB Perspective Only:**
```json
{
    "query_id": "P56868",
    "view": "pdb"
}
```

**Request Example - Both Perspectives:**
```json
{
    "query_id": "P56868",
    "view": "both"
}
```

**curl Example:**
```bash
# UniProt perspective
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "uniprot"}'

# PDB perspective
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "pdb"}'

# Both perspectives
curl -X POST http://localhost:18919/api/enzyme/active_sites \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868", "view": "both"}'
```

**Response Example (UniProt Perspective):**
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

**Response Example (PDB Perspective):**
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

### 4. Query Catalytic Mechanism Summary

**Endpoint:** `POST /api/enzyme/mechanism/summary`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/mechanism/summary \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response Example:**
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

### 5. Query Detailed Mechanism Steps

**Endpoint:** `POST /api/enzyme/mechanism/steps`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/mechanism/steps \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response Example:**
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

### 6. Search Enzymes by Name

**Endpoint:** `POST /api/enzyme/search`

**Request Parameters:**
- `name` (required): Enzyme name (supports fuzzy matching)
- `limit` (optional): Maximum number of results, default 10, range 1-100

**Request:**
```json
{
    "name": "lactamase",
    "limit": 5
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/search \
  -H "Content-Type: application/json" \
  -d '{"name": "lactamase", "limit": 5}'
```

**Response Example:**
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

### 7. Paginate Through All Enzymes

**Endpoint:** `POST /api/enzyme/list`

**Request Parameters:**
- `page` (optional): Page number, default 1
- `per_page` (optional): Number per page, default 50, range 1-100

**Request:**
```json
{
    "page": 1,
    "per_page": 10
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/list \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "per_page": 10}'
```

**Response Example:**
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

### 8. Get All Identifiers for an Enzyme

**Endpoint:** `POST /api/enzyme/identifiers`

**Request:**
```json
{
    "query_id": "P56868"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:18919/api/enzyme/identifiers \
  -H "Content-Type: application/json" \
  -d '{"query_id": "P56868"}'
```

**Response Example:**
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

## 🐍 Python Code Examples

### Complete Client Class

```python
import requests
from typing import Optional, Dict, List, Any


class MCSAClient:
    """M-CSA Enzyme Query Client - Compatible with LLM Function Call"""
    
    def __init__(self, base_url: str = "http://localhost:18919"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
    
    def _post(self, endpoint: str, data: dict) -> dict:
        """Send POST request"""
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # ========== Complete Query ==========
    
    def query(self, query_id: str) -> dict:
        """
        Query complete enzyme information
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
        """
        return self._post("/api/enzyme/query", {"query_id": query_id})
    
    # ========== Reaction Query ==========
    
    def get_reaction(self, query_id: str) -> dict:
        """
        Query reaction information (reactants and products)
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
        """
        return self._post("/api/enzyme/reaction", {"query_id": query_id})
    
    # ========== Active Sites Query ==========
    
    def get_active_sites(
        self, 
        query_id: str, 
        view: str = "both"
    ) -> dict:
        """
        Query active sites
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            view: Perspective - "uniprot", "pdb", or "both"
        """
        return self._post("/api/enzyme/active_sites", {
            "query_id": query_id,
            "view": view
        })
    
    # ========== Mechanism Query ==========
    
    def get_mechanism_summary(self, query_id: str) -> dict:
        """
        Query catalytic mechanism summary
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
        """
        return self._post("/api/enzyme/mechanism/summary", {"query_id": query_id})
    
    def get_mechanism_steps(self, query_id: str) -> dict:
        """
        Query detailed mechanism steps
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
        """
        return self._post("/api/enzyme/mechanism/steps", {"query_id": query_id})
    
    # ========== Search and List ==========
    
    def search(self, name: str, limit: int = 10) -> list:
        """
        Search enzymes by name
        
        Args:
            name: Enzyme name (supports fuzzy matching)
            limit: Maximum number of results
        """
        return self._post("/api/enzyme/search", {"name": name, "limit": limit})
    
    def list_enzymes(self, page: int = 1, per_page: int = 50) -> dict:
        """
        Paginate through all enzymes
        
        Args:
            page: Page number
            per_page: Number per page
        """
        return self._post("/api/enzyme/list", {"page": page, "per_page": per_page})
    
    # ========== Identifiers Query ==========
    
    def get_identifiers(self, query_id: str) -> dict:
        """
        Get all identifiers for an enzyme
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
        """
        return self._post("/api/enzyme/identifiers", {"query_id": query_id})


# ========== Usage Examples ==========

if __name__ == "__main__":
    client = MCSAClient()
    
    # 1. Query reaction
    reaction = client.get_reaction("P56868")
    print("=== Reaction Information ===")
    print(f"Enzyme name: {reaction['enzyme_name']}")
    print(f"EC number: {reaction['reaction']['ec']}")
    print(f"Reactants: {[r['name'] for r in reaction['reaction']['reactants']]}")
    print(f"Products: {[p['name'] for p in reaction['reaction']['products']]}")
    
    # 2. Query active sites (UniProt perspective)
    sites = client.get_active_sites("P56868", view="uniprot")
    print("\n=== Active Sites (UniProt) ===")
    for site in sites["active_sites_uniprot"]:
        print(f"  {site['code']}{site['resid']}: {', '.join(site['roles'])}")
    
    # 3. Query mechanism summary
    summary = client.get_mechanism_summary("P56868")
    print("\n=== Mechanism Summary ===")
    print(summary["summary_text"])
    
    # 4. Query mechanism steps
    steps = client.get_mechanism_steps("P56868")
    print("\n=== Mechanism Steps ===")
    for step in steps["steps"]:
        print(f"Step {step['step_id']}: {step['description']}")
```

---

## 🤖 LLM Function Call Integration

### OpenAI Function Calling Format

```json
{
    "name": "query_enzyme_reaction",
    "description": "Query enzyme reaction information including reactants and products",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier, can be MCSA ID, UniProt ID or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_active_sites",
    "description": "Query enzyme active site information",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier, can be MCSA ID, UniProt ID or PDB ID"
            },
            "view": {
                "type": "string",
                "enum": ["uniprot", "pdb", "both"],
                "description": "Perspective selection: uniprot (UniProt sequence position), pdb (PDB structure position), both (return both)"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_mechanism_summary",
    "description": "Query enzyme catalytic mechanism summary",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier, can be MCSA ID, UniProt ID or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

```json
{
    "name": "query_enzyme_mechanism_steps",
    "description": "Query detailed steps of enzyme catalytic mechanism",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "Enzyme identifier, can be MCSA ID, UniProt ID or PDB ID"
            }
        },
        "required": ["query_id"]
    }
}
```

---

## 📊 Response Fields Reference

### Reaction (Reaction) Fields

| Field | Type | Description |
|------|------|------|
| `reaction.ec` | string | EC classification number |
| `reaction.is_polymeric` | bool | Whether is polymeric reaction |
| `reaction.reactants` | list | List of reactants |
| `reaction.reactants[].name` | string | Compound name |
| `reaction.reactants[].chebi_id` | string | ChEBI ID |
| `reaction.products` | list | List of products |

### Active Sites (Active Sites) Fields

| Field | Type | Description |
|------|------|------|
| `active_sites_uniprot[].code` | string | Amino acid three-letter code |
| `active_sites_uniprot[].resid` | int | Position in UniProt sequence |
| `active_sites_uniprot[].roles` | list | List of functional roles |
| `active_sites_pdb[].pdb_id` | string | PDB ID |
| `active_sites_pdb[].chain` | string | Chain name |
| `active_sites_pdb[].resid` | int | Position in PDB structure |

### Mechanism (Mechanism) Fields

| Field | Type | Description |
|------|------|------|
| `summary_text` | string | Mechanism summary text |
| `components_summary` | string | Mechanism components summary |
| `is_detailed` | bool | Whether has detailed mechanism |
| `rating` | int | Confidence rating |
| `steps[].step_id` | int | Step number |
| `steps[].description` | string | Step description |
| `steps[].is_product` | bool | Whether produces final products |

---

## Technology Stack

- Python 3.10+
- FastAPI
- SQLAlchemy (ORM 2.0)
- SQLite
- Pydantic
- Uvicorn
