"""
M-CSA Enzyme Query Microservice

FastAPI-based microservice for querying enzyme mechanism data from M-CSA database.
All endpoints accept JSON request body for LLM function call integration.

Usage:
    uvicorn main:app --reload --host 0.0.0.0 --port 18919
"""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from enum import Enum

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from retriever import EnzymeRetriever


# Initialize FastAPI app
app = FastAPI(
    title="M-CSA Enzyme Query Service",
    description="""
    A microservice for querying enzyme catalytic mechanism data from the M-CSA database.
    
    ## Design Principles
    **All endpoints use POST method with JSON body parameters**, facilitating integration with LLM Function Call capabilities.
    
    ## Features
    - Query by MCSA ID, UniProt ID, or PDB ID
    - Get comprehensive enzyme information including active sites, reactions, mechanisms, and cofactors
    - **Fine-grained queries**: Retrieve reactions, active sites, mechanism summary, mechanism steps, or cofactors individually
    - **Electron flow queries**: Retrieve detailed electron movement information for each mechanism step
    - Search enzymes by name
    - List all enzymes with pagination
    
    ## Identifier Formats
    - **MCSA ID**: Numeric (e.g., `1`, `123`) or prefixed (e.g., `M1`, `MCSA:1`)
    - **UniProt ID**: Standard format (e.g., `P56868`, `P62593`)
    - **PDB ID**: 4-character code (e.g., `1b73`, `2FQX`)
    """,
    version="2.2.0",
    contact={
        "name": "M-CSA Query Service",
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize retriever
DB_PATH = Path(__file__).parent / "db" / "mcsa.db"
retriever = EnzymeRetriever(str(DB_PATH))


# ==============================================================================
# Enums
# ==============================================================================

class ActiveSiteView(str, Enum):
    """View perspective for active sites."""
    UNIPROT = "uniprot"
    PDB = "pdb"
    BOTH = "both"


# ==============================================================================
# Pydantic Models for Request
# ==============================================================================

class QueryRequest(BaseModel):
    """Request model for enzyme query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )


class ReactionQueryRequest(BaseModel):
    """Request model for reaction query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )
    include_smiles: bool = Field(
        default=False,
        description="Whether to include SMILES strings for compounds in the response"
    )


class ActiveSitesQueryRequest(BaseModel):
    """Request model for active sites query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )
    view: ActiveSiteView = Field(
        default=ActiveSiteView.BOTH,
        description="Perspective for active sites: 'uniprot', 'pdb', or 'both'"
    )
    include_sequence: bool = Field(
        default=False,
        description="Whether to include the protein sequence in the response"
    )


class CofactorsQueryRequest(BaseModel):
    """Request model for cofactors query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )
    include_smiles: bool = Field(
        default=False,
        description="Whether to include SMILES strings for cofactors in the response"
    )


class MechanismQueryRequest(BaseModel):
    """Request model for mechanism query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )
    include_steps: bool = Field(
        default=True,
        description="Whether to include detailed mechanism steps"
    )


class ElectronFlowQueryRequest(BaseModel):
    """Request model for electron flow query."""
    query_id: str = Field(
        ...,
        description="Identifier to search for (MCSA ID, UniProt ID, or PDB ID)",
        examples=["P56868", "1", "1b73"]
    )
    mechanism_id: Optional[int] = Field(
        default=None,
        description="Optional mechanism ID to filter by specific mechanism (useful when enzyme has multiple mechanisms)"
    )
    step_index: Optional[int] = Field(
        default=None,
        description="Optional step index to retrieve specific step (0=reactant, 1=step1, 2=step2, etc.)"
    )
    include_cxsmiles: bool = Field(
        default=False,
        description="Whether to include CXSMILES strings for each step"
    )


class SearchRequest(BaseModel):
    """Request model for enzyme name search."""
    name: str = Field(
        ...,
        description="Enzyme name to search for (partial match supported)",
        examples=["racemase", "lactamase"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )


class ListRequest(BaseModel):
    """Request model for listing enzymes."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=50, ge=1, le=100, description="Results per page")


class IdentifiersRequest(BaseModel):
    """Request model for getting identifiers."""
    query_id: str = Field(
        ...,
        description="Any identifier (MCSA ID, UniProt ID, or PDB ID) to find related identifiers",
        examples=["P56868", "1", "1b73"]
    )


# ==============================================================================
# Pydantic Models for Response
# ==============================================================================

class BasicInfo(BaseModel):
    """Basic enzyme information."""
    mcsa_id: int
    enzyme_name: str
    description: Optional[str] = None
    reference_uniprot_id: Optional[str] = None
    ec_numbers: List[str] = []
    url: Optional[str] = None


class ActiveSiteUniProt(BaseModel):
    """Active site with UniProt position."""
    uniprot_id: str
    code: str
    resid: int
    is_reference: bool
    roles: List[str]
    roles_summary: Optional[str] = None
    main_annotation: Optional[str] = None


class ActiveSitePDB(BaseModel):
    """Active site with PDB position."""
    pdb_id: str
    chain: str
    code: str
    resid: int
    auth_resid: Optional[int] = None
    is_reference: bool
    domain_name: Optional[str] = None
    domain_cath_id: Optional[str] = None
    roles: List[str]
    roles_summary: Optional[str] = None
    main_annotation: Optional[str] = None


class Compound(BaseModel):
    """Reaction compound (reactant or product)."""
    name: str
    count: int = 1
    chebi_id: Optional[str] = None
    smiles: Optional[str] = None


class ReactionInfo(BaseModel):
    """Reaction information."""
    ec: Optional[str] = None
    is_polymeric: bool = False
    reactants: List[Compound] = []
    products: List[Compound] = []


class MechanismStep(BaseModel):
    """Single step in the mechanism."""
    step_id: int
    description: str
    is_product: bool = False
    figure: Optional[str] = None


class MechanismInfo(BaseModel):
    """Mechanism information."""
    mechanism_id: Optional[int] = None
    summary_text: Optional[str] = None
    is_detailed: bool = False
    rating: Optional[int] = None
    components_summary: Optional[str] = None
    steps: List[MechanismStep] = []
    mechanisms: Optional[List[dict]] = None  # For multiple mechanisms
    references: List[Dict[str, Any]] = Field(default_factory=list)


class CofactorRoleInfo(BaseModel):
    """Cofactor role information."""
    role: str
    role_type: Optional[str] = None
    role_group: Optional[str] = None


class CofactorInfo(BaseModel):
    """Cofactor information."""
    pdb_code: str
    name: Optional[str] = None
    chebi_id: Optional[str] = None
    kegg_compound: Optional[str] = None
    uniprot_id: Optional[str] = None
    pdb_id: Optional[str] = None
    ec: Optional[str] = None
    roles: List[CofactorRoleInfo] = []
    smiles: Optional[str] = None


class EnzymeInfoResponse(BaseModel):
    """Complete enzyme information response."""
    found: bool = True
    message: str = "Query successful"
    basic_info: Optional[BasicInfo] = None
    active_sites_uniprot: List[ActiveSiteUniProt] = []
    active_sites_pdb: List[ActiveSitePDB] = []
    reaction: Optional[ReactionInfo] = None
    mechanism: Optional[MechanismInfo] = None
    cofactors: List[CofactorInfo] = []
    sequence_info: Optional[Dict[str, Any]] = None


class ReactionResponse(BaseModel):
    """Response for reaction query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    reaction: Optional[ReactionInfo] = None


class ActiveSitesResponse(BaseModel):
    """Response for active sites query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    view: str = "both"
    active_sites_uniprot: Optional[List[ActiveSiteUniProt]] = None
    active_sites_pdb: Optional[List[ActiveSitePDB]] = None
    sequence: Optional[str] = None


class MechanismSummaryResponse(BaseModel):
    """Response for mechanism summary query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    summary_text: Optional[str] = None
    components_summary: Optional[str] = None
    is_detailed: bool = False
    rating: Optional[int] = None


class MechanismStepsResponse(BaseModel):
    """Response for mechanism steps query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    summary_text: Optional[str] = None
    steps: List[MechanismStep] = []


class ElectronFlowSource(BaseModel):
    """Electron flow source information."""
    type: str = Field(description="Source type: 'atom', 'bond', or 'lone_pair'")
    description_cxsmiles: Optional[str] = Field(None, description="Human-readable description with CXSMILES indices")
    cxsmiles_index: Optional[int] = Field(None, description="Atom index in CXSMILES (for atom type)")
    element: Optional[str] = Field(None, description="Element symbol")
    
    class Config:
        extra = "allow"  # Allow additional fields for different source types


class ElectronFlowTarget(BaseModel):
    """Electron flow target information."""
    type: str = Field(description="Target type: 'atom', 'atom_pair', or 'bond'")
    description_cxsmiles: Optional[str] = Field(None, description="Human-readable description with CXSMILES indices")
    
    class Config:
        extra = "allow"  # Allow additional fields for different target types


class ElectronFlow(BaseModel):
    """Single electron flow in a mechanism step."""
    index: int = Field(description="Index of this electron flow within the step")
    electron_count: int = Field(description="Number of electrons transferred (1 for single, 2 for pair)")
    arrow_type: str = Field(description="Arrow type: 'electron_pair' or 'single_electron'")
    arrow_type_cn: Optional[str] = Field(None, description="Arrow type description in Chinese")
    source: dict = Field(description="Source of electron flow (atom, bond, or lone pair)")
    target: dict = Field(description="Target of electron flow (atom or atom pair for new bond)")


class ParsedMechanismStep(BaseModel):
    """Parsed mechanism step with electron flow information."""
    step_index: int = Field(description="Step index (0=reactant, 1=step1, etc.)")
    role: str = Field(description="Role of this step: 'reactant', 'intermediate', or 'product'")
    description: Optional[str] = Field(None, description="Step description text")
    mechanism_id: int = Field(description="Mechanism ID this step belongs to")
    processing_status: str = Field(default="success", description="Processing status: 'success', 'warning', or 'error'. If not 'success', electron_flows may be empty or incomplete.")
    status_message: Optional[str] = Field(None, description="Status message explaining why data conversion failed (only present when processing_status is not 'success')")
    electron_flows: List[dict] = Field(default=[], description="List of electron flows in this step")
    involved_residues: List[str] = Field(default=[], description="List of catalytic residues involved in this step")
    cxsmiles: Optional[str] = Field(None, description="CXSMILES string representing the molecular structure")
    alignment_match_rate: Optional[float] = Field(None, description="Atom alignment quality score (0-1)")
    alignment_warnings: Optional[str] = Field(None, description="Warnings from atom alignment process")


class ElectronFlowResponse(BaseModel):
    """Response for electron flow query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    total_steps: int = 0
    steps: List[ParsedMechanismStep] = []


class MechanismSummaryInfo(BaseModel):
    """Summary info for a single mechanism."""
    mechanism_id: int
    step_count: int
    steps_with_electron_flows: int
    involved_residues: List[str] = []


class ElectronFlowSummaryResponse(BaseModel):
    """Response for electron flow summary query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    mechanism_count: int = 0
    all_involved_residues: List[str] = []
    mechanisms: List[MechanismSummaryInfo] = []


class EnzymeListItem(BaseModel):
    """Brief enzyme info for list responses."""
    mcsa_id: int
    enzyme_name: str
    reference_uniprot_id: Optional[str] = None


class ListResponse(BaseModel):
    """Paginated list response."""
    total: int
    page: int
    per_page: int
    total_pages: int
    results: List[EnzymeListItem]


class IdentifiersResponse(BaseModel):
    """Response for identifiers query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    mcsa_id: Optional[int] = None
    identifiers: Dict[str, List[str]] = {}


class CofactorsResponse(BaseModel):
    """Response for cofactors query."""
    found: bool = True
    message: str = "Query successful"
    query_id: str
    enzyme_name: Optional[str] = None
    mcsa_id: Optional[int] = None
    cofactors: List[CofactorInfo] = []


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# ==============================================================================
# API Endpoints - System
# ==============================================================================

@app.post("/", response_model=SuccessResponse)
async def root():
    """
    Root endpoint with API information.
    
    **Request Body:** (empty or {})
    """
    return SuccessResponse(
        success=True,
        message="M-CSA Enzyme Query Service is running",
        data={
            "version": "2.2.0",
            "endpoints": {
                "query_full": "/api/enzyme/query",
                "query_reaction": "/api/enzyme/reaction",
                "query_active_sites": "/api/enzyme/active_sites",
                "query_mechanism_summary": "/api/enzyme/mechanism/summary",
                "query_mechanism_steps": "/api/enzyme/mechanism/steps",
                "query_electron_flows": "/api/enzyme/mechanism/electron_flows",
                "query_electron_flows_summary": "/api/enzyme/mechanism/electron_flows/summary",
                "query_cofactors": "/api/enzyme/cofactors",
                "search": "/api/enzyme/search",
                "list": "/api/enzyme/list",
                "identifiers": "/api/enzyme/identifiers"
            }
        }
    )


@app.post("/health", response_model=SuccessResponse)
async def health_check():
    """
    Health check endpoint.
    
    **Request Body:** (empty or {})
    """
    return SuccessResponse(
        success=True,
        message="Service is healthy"
    )


# ==============================================================================
# API Endpoints - Full Query
# ==============================================================================

@app.post("/api/enzyme/query", response_model=EnzymeInfoResponse)
async def query_enzyme(request: QueryRequest):
    """
    Query complete enzyme information by identifier.
    
    Returns comprehensive enzyme information including:
    - Basic info (name, description, EC numbers)
    - Active sites (UniProt and PDB perspectives)
    - Reaction (reactants and products)
    - Mechanism (summary and steps)
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868"
    }
    ```
    """
    result = retriever.get_enzyme_info(request.query_id, include_smiles=True, include_visualization=True)
    
    if result is None:
        return EnzymeInfoResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}'. Please verify the input; supported identifiers include MCSA ID (e.g., '1'), UniProt ID (e.g., 'P56868'), or PDB ID (e.g., '1b73')."
        )
    
    # 添加成功状态信息
    result["found"] = True
    result["message"] = f"Successfully retrieved full information for enzyme '{result['basic_info']['enzyme_name']}' (MCSA ID: {result['basic_info']['mcsa_id']})."
    return result


# ==============================================================================
# API Endpoints - Reaction Query
# ==============================================================================

@app.post("/api/enzyme/reaction", response_model=ReactionResponse)
async def query_reaction(request: ReactionQueryRequest):
    """
    Query reaction information (reactants and products) for an enzyme.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868",
        "include_smiles": false
    }
    ```
    
    **Response includes:**
    - EC number
    - Reactants list with names and ChEBI IDs
    - Products list with names and ChEBI IDs
    - SMILES strings (if include_smiles is true)
    """
    result = retriever.get_enzyme_info(request.query_id, include_smiles=request.include_smiles)
    
    if result is None:
        return ReactionResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so reaction information cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    reaction = result.get("reaction")
    enzyme_name = result["basic_info"]["enzyme_name"]
    mcsa_id = result["basic_info"]["mcsa_id"]
    
    if reaction is None:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no reaction information is recorded."
    else:
        reactants_count = len(reaction.get("reactants", []))
        products_count = len(reaction.get("products", []))
        smiles_info = " (with SMILES)" if request.include_smiles else ""
        message = f"Successfully retrieved reaction information for enzyme '{enzyme_name}': includes {reactants_count} reactants and {products_count} products{smiles_info}."
    
    return ReactionResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        reaction=reaction
    )


# ==============================================================================
# API Endpoints - Active Sites Query
# ==============================================================================

@app.post("/api/enzyme/active_sites", response_model=ActiveSitesResponse)
async def query_active_sites(request: ActiveSitesQueryRequest):
    """
    Query active site residues for an enzyme.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868",
        "view": "both",
        "include_sequence": false
    }
    ```
    
    **view options:**
    - `"uniprot"`: UniProt perspective (residue numbering based on UniProt sequence)
    - `"pdb"`: PDB perspective (includes chain and structure information)
    - `"both"`: Both perspectives (default)
    
    **Response includes:**
    - Residue code (amino acid type, e.g., "Asp", "Cys")
    - Residue position number
    - Functional roles (e.g., "proton donor", "nucleophile")
    - Protein sequence (if include_sequence is true)
    """
    result = retriever.get_enzyme_info(request.query_id)
    
    if result is None:
        return ActiveSitesResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so active site information cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id,
            view=request.view.value
        )
    
    enzyme_name = result["basic_info"]["enzyme_name"]
    mcsa_id = result["basic_info"]["mcsa_id"]
    
    active_sites_uniprot = None
    active_sites_pdb = None
    site_counts = []
    
    if request.view in [ActiveSiteView.UNIPROT, ActiveSiteView.BOTH]:
        active_sites_uniprot = result.get("active_sites_uniprot", [])
        site_counts.append(f"UniProt view: {len(active_sites_uniprot)} residues")
    
    if request.view in [ActiveSiteView.PDB, ActiveSiteView.BOTH]:
        active_sites_pdb = result.get("active_sites_pdb", [])
        site_counts.append(f"PDB view: {len(active_sites_pdb)} residues")
    
    # Get sequence if requested
    sequence = None
    if request.include_sequence:
        seq_result = retriever.get_sequence(request.query_id)
        if seq_result:
            sequence = seq_result.get("sequence")
    
    total_sites = len(active_sites_uniprot or []) + len(active_sites_pdb or [])
    if total_sites == 0:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no active site information is recorded."
    else:
        seq_info = " (with sequence)" if sequence else ""
        message = f"Successfully retrieved active site information for enzyme '{enzyme_name}' ({', '.join(site_counts)}){seq_info}."
    
    return ActiveSitesResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        view=request.view.value,
        active_sites_uniprot=active_sites_uniprot,
        active_sites_pdb=active_sites_pdb,
        sequence=sequence
    )


# ==============================================================================
# API Endpoints - Mechanism Query
# ==============================================================================

@app.post("/api/enzyme/mechanism/summary", response_model=MechanismSummaryResponse)
async def query_mechanism_summary(request: QueryRequest):
    """
    Query mechanism summary (overview) for an enzyme.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868"
    }
    ```
    
    **Response includes:**
    - summary_text: Overview of the catalytic mechanism
    - components_summary: Key mechanistic components
    - is_detailed: Whether detailed mechanism information is available
    - rating: Confidence rating of the mechanism
    """
    result = retriever.get_enzyme_info(request.query_id)
    
    if result is None:
        return MechanismSummaryResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so mechanism summary information cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    enzyme_name = result["basic_info"]["enzyme_name"]
    mcsa_id = result["basic_info"]["mcsa_id"]
    mechanism = result.get("mechanism") or {}
    
    summary_text = mechanism.get("summary_text")
    if not summary_text and not mechanism.get("components_summary"):
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no mechanism summary information is available."
    else:
        detail_status = "detailed mechanism" if mechanism.get("is_detailed") else "basic mechanism"
        rating = mechanism.get("rating")
        rating_info = f", confidence rating: {rating}" if rating else ""
        message = f"Successfully retrieved a {detail_status} summary for enzyme '{enzyme_name}'{rating_info}."
    
    return MechanismSummaryResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        summary_text=summary_text,
        components_summary=mechanism.get("components_summary"),
        is_detailed=mechanism.get("is_detailed", False),
        rating=mechanism.get("rating")
    )


@app.post("/api/enzyme/mechanism/steps", response_model=MechanismStepsResponse)
async def query_mechanism_steps(request: QueryRequest):
    """
    Query detailed mechanism steps for an enzyme.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868"
    }
    ```
    
    **Response includes:**
    - summary_text: Overview of the catalytic mechanism
    - steps: List of mechanism steps with:
        - step_id: Step number
        - description: Detailed description of the step
        - is_product: Whether this step produces the final product
        - figure: URL to mechanism diagram (if available)
    """
    result = retriever.get_enzyme_info(request.query_id)
    
    if result is None:
        return MechanismStepsResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so mechanism steps cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    enzyme_name = result["basic_info"]["enzyme_name"]
    mcsa_id = result["basic_info"]["mcsa_id"]
    mechanism = result.get("mechanism") or {}
    steps = mechanism.get("steps", [])
    
    if not steps:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no detailed mechanism steps are available."
    else:
        message = f"Successfully retrieved the mechanism for enzyme '{enzyme_name}' with {len(steps)} steps."
    
    return MechanismStepsResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        summary_text=mechanism.get("summary_text"),
        steps=steps
    )


# ==============================================================================
# API Endpoints - Electron Flow Query
# ==============================================================================

@app.post("/api/enzyme/mechanism/electron_flows", response_model=ElectronFlowResponse)
async def query_electron_flows(request: ElectronFlowQueryRequest):
    """
    Query electron flow information for mechanism steps.
    
    This endpoint returns detailed electron flow data extracted from mechanism diagrams,
    showing how electrons move between atoms during each catalytic step. This is essential
    for understanding the molecular-level details of enzyme catalysis.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868",
        "mechanism_id": null,
        "step_index": null,
        "include_cxsmiles": true
    }
    ```
    
    **Parameters:**
    - `query_id`: MCSA ID, UniProt ID, or PDB ID
    - `mechanism_id`: Optional - filter by specific mechanism (for enzymes with multiple mechanisms)
    - `step_index`: Optional - get specific step only (0=reactant, 1=step1, etc.)
    - `include_cxsmiles`: Whether to include CXSMILES molecular representations
    
    **Response includes:**
    - steps: List of parsed mechanism steps with:
        - step_index: Step number (0=reactant)
        - role: 'reactant', 'intermediate', or 'product'
        - electron_flows: Array of electron movements with source and target
        - involved_residues: List of catalytic residues involved
        - cxsmiles: ChemAxon Extended SMILES representation
    """
    result = retriever.get_mechanism_electron_flows(
        request.query_id,
        mechanism_id=request.mechanism_id,
        step_index=request.step_index,
        include_cxsmiles=request.include_cxsmiles
    )
    
    if result is None:
        return ElectronFlowResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so electron flow information cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    enzyme_name = result["enzyme_name"]
    mcsa_id = result["mcsa_id"]
    steps = result.get("steps", [])
    total_steps = result.get("total_steps", 0)
    
    if not steps:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no parsed electron flow information is available."
    else:
        # Count steps by status
        success_steps = sum(1 for s in steps if s.get("processing_status") == "success")
        warning_steps = sum(1 for s in steps if s.get("processing_status") == "warning")
        error_steps = sum(1 for s in steps if s.get("processing_status") == "error")
        steps_with_flows = sum(1 for s in steps if s.get("electron_flows"))
        
        filter_info = []
        if request.mechanism_id is not None:
            filter_info.append(f"mechanism {request.mechanism_id}")
        if request.step_index is not None:
            filter_info.append(f"step {request.step_index}")
        filter_str = f" (filtered by {', '.join(filter_info)})" if filter_info else ""
        
        # Build status info
        status_parts = []
        if success_steps > 0:
            status_parts.append(f"{success_steps} successful")
        if warning_steps > 0:
            status_parts.append(f"{warning_steps} with warnings")
        if error_steps > 0:
            status_parts.append(f"{error_steps} failed")
        status_info = f" ({', '.join(status_parts)})" if (warning_steps > 0 or error_steps > 0) else ""
        
        message = f"Successfully retrieved electron flow information for enzyme '{enzyme_name}': {total_steps} steps{filter_str}{status_info}, {steps_with_flows} with electron flow data."
    
    return ElectronFlowResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        total_steps=total_steps,
        steps=steps
    )


@app.post("/api/enzyme/mechanism/electron_flows/summary", response_model=ElectronFlowSummaryResponse)
async def query_electron_flow_summary(request: QueryRequest):
    """
    Get a summary of electron flow information for an enzyme's mechanisms.
    
    Returns an overview of all mechanisms including step counts and involved catalytic residues,
    without the detailed electron flow data. Useful for getting a quick overview before
    requesting detailed electron flow information.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868"
    }
    ```
    
    **Response includes:**
    - mechanism_count: Number of mechanisms for this enzyme
    - all_involved_residues: Combined list of all catalytic residues involved
    - mechanisms: List with per-mechanism summary:
        - mechanism_id: Mechanism identifier
        - step_count: Total number of steps
        - steps_with_electron_flows: Steps that have electron flow data
        - involved_residues: Residues involved in this mechanism
    """
    result = retriever.get_mechanism_electron_flow_summary(request.query_id)
    
    if result is None:
        return ElectronFlowSummaryResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so electron flow summary cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    enzyme_name = result["enzyme_name"]
    mcsa_id = result["mcsa_id"]
    mechanism_count = result.get("mechanism_count", 0)
    mechanisms = result.get("mechanisms", [])
    all_residues = result.get("all_involved_residues", [])
    
    if mechanism_count == 0:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no parsed mechanism data is available."
    else:
        total_steps = sum(m.get("step_count", 0) for m in mechanisms)
        residue_info = f", involving {len(all_residues)} catalytic residues" if all_residues else ""
        message = f"Successfully retrieved electron flow summary for enzyme '{enzyme_name}': {mechanism_count} mechanism(s) with {total_steps} total steps{residue_info}."
    
    return ElectronFlowSummaryResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        mechanism_count=mechanism_count,
        all_involved_residues=all_residues,
        mechanisms=mechanisms
    )


# ==============================================================================
# API Endpoints - Cofactors Query
# ==============================================================================

@app.post("/api/enzyme/cofactors", response_model=CofactorsResponse)
async def query_cofactors(request: CofactorsQueryRequest):
    """
    Query cofactor information for an enzyme.
    
    Cofactors are non-protein molecules that assist in enzyme catalysis,
    such as FAD, NAD, metal ions (Cu, Zn), etc.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868",
        "include_smiles": false
    }
    ```
    
    **Response includes:**
    - cofactors: List of cofactors with:
        - pdb_code: Cofactor abbreviation (e.g., "FAD", "NAD", "CU")
        - name: Full cofactor name
        - chebi_id: ChEBI identifier
        - kegg_compound: KEGG compound ID
        - roles: List of functional roles in the mechanism
        - smiles: SMILES string (if include_smiles is true)
    """
    result = retriever.get_cofactors(request.query_id, include_smiles=request.include_smiles)
    
    if result is None:
        return CofactorsResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so cofactor information cannot be retrieved. Please verify the identifier.",
            query_id=request.query_id
        )
    
    enzyme_name = result["enzyme_name"]
    mcsa_id = result["mcsa_id"]
    cofactors = result.get("cofactors", [])
    
    if not cofactors:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no cofactor information is recorded for this enzyme."
    else:
        cofactor_names = [c.get("pdb_code") or c.get("name") for c in cofactors]
        smiles_info = " (with SMILES)" if request.include_smiles else ""
        message = f"Successfully retrieved cofactor information for enzyme '{enzyme_name}': {len(cofactors)} cofactor(s) found ({', '.join(cofactor_names[:5])}{'...' if len(cofactor_names) > 5 else ''}){smiles_info}."
    
    return CofactorsResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        cofactors=cofactors
    )


# ==============================================================================
# API Endpoints - Search and List
# ==============================================================================

@app.post("/api/enzyme/search", response_model=List[EnzymeListItem])
async def search_enzymes(request: SearchRequest):
    """
    Search enzymes by name.
    
    Supports partial matching. Returns a list of matching enzymes.
    
    **Request Body:**
    ```json
    {
        "name": "racemase",
        "limit": 10
    }
    ```
    """
    results = retriever.search_by_name(request.name, request.limit)
    return results


@app.post("/api/enzyme/list", response_model=ListResponse)
async def list_enzymes(request: ListRequest):
    """
    List all enzymes with pagination.
    
    **Request Body:**
    ```json
    {
        "page": 1,
        "per_page": 50
    }
    ```
    """
    results = retriever.list_all_enzymes(request.page, request.per_page)
    return results


# ==============================================================================
# API Endpoints - Identifiers
# ==============================================================================

@app.post("/api/enzyme/identifiers", response_model=IdentifiersResponse)
async def get_identifiers(request: IdentifiersRequest):
    """
    Get all identifiers for an enzyme.
    
    Given any identifier (MCSA ID, UniProt ID, or PDB ID), returns all associated identifiers.
    
    **Request Body:**
    ```json
    {
        "query_id": "P56868"
    }
    ```
    
    **Response includes:**
    - mcsa: List of MCSA IDs
    - uniprot: List of UniProt IDs
    - pdb: List of PDB IDs
    """
    # First find the MCSA ID
    result = retriever.get_enzyme_info(request.query_id)
    
    if result is None:
        return IdentifiersResponse(
            found=False,
            message=f"No enzyme found matching identifier '{request.query_id}', so related identifiers cannot be retrieved. Please verify the identifier; supported types include MCSA ID, UniProt ID, and PDB ID.",
            query_id=request.query_id
        )
    
    mcsa_id = result["basic_info"]["mcsa_id"]
    enzyme_name = result["basic_info"]["enzyme_name"]
    identifiers = retriever.get_identifiers(mcsa_id)
    
    # 构建标识符统计信息
    id_summary = []
    for id_type, id_list in identifiers.items():
        if id_list:
            id_summary.append(f"{id_type}: {len(id_list)} 个")
    
    message = f"Successfully retrieved all related identifiers for enzyme '{enzyme_name}' ({', '.join(id_summary)})."
    
    return IdentifiersResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        mcsa_id=mcsa_id,
        identifiers=identifiers
    )


# ==============================================================================
# Run Application
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18919)
