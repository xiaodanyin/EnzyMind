"""
M-CSA Enzyme Query Microservice

FastAPI-based microservice for querying enzyme mechanism data from M-CSA database.
All endpoints accept JSON request body for LLM function call integration.

Usage:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
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
    
    ## 设计原则
    **所有端点均使用 POST 方法，通过 JSON body 传递参数**，便于与大语言模型的 Function Call 功能集成。
    
    ## Features
    - Query by MCSA ID, UniProt ID, or PDB ID
    - Get comprehensive enzyme information including active sites, reactions, and mechanisms
    - **细粒度查询**: 单独获取反应、活性位点、机理概括、机理步骤
    - Search enzymes by name
    - List all enzymes with pagination
    
    ## Identifier Formats
    - **MCSA ID**: Numeric (e.g., `1`, `123`) or prefixed (e.g., `M1`, `MCSA:1`)
    - **UniProt ID**: Standard format (e.g., `P56868`, `P62593`)
    - **PDB ID**: 4-character code (e.g., `1b73`, `2FQX`)
    """,
    version="2.0.0",
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


class Compound(BaseModel):
    """Reaction compound (reactant or product)."""
    name: str
    count: int = 1
    chebi_id: Optional[str] = None


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


class EnzymeInfoResponse(BaseModel):
    """Complete enzyme information response."""
    found: bool = True
    message: str = "Query successful"
    basic_info: Optional[BasicInfo] = None
    active_sites_uniprot: List[ActiveSiteUniProt] = []
    active_sites_pdb: List[ActiveSitePDB] = []
    reaction: Optional[ReactionInfo] = None
    mechanism: Optional[MechanismInfo] = None


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
            "version": "2.0.0",
            "endpoints": {
                "query_full": "/api/enzyme/query",
                "query_reaction": "/api/enzyme/reaction",
                "query_active_sites": "/api/enzyme/active_sites",
                "query_mechanism_summary": "/api/enzyme/mechanism/summary",
                "query_mechanism_steps": "/api/enzyme/mechanism/steps",
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
    result = retriever.get_enzyme_info(request.query_id)
    
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
        "query_id": "P56868"
    }
    ```
    
    **Response includes:**
    - EC number
    - Reactants list with names and ChEBI IDs
    - Products list with names and ChEBI IDs
    """
    result = retriever.get_enzyme_info(request.query_id)
    
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
        message = f"Successfully retrieved reaction information for enzyme '{enzyme_name}': includes {reactants_count} reactants and {products_count} products."
    
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
        "view": "both"
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
        site_counts.append(f"UniProt视角: {len(active_sites_uniprot)} 个残基")
    
    if request.view in [ActiveSiteView.PDB, ActiveSiteView.BOTH]:
        active_sites_pdb = result.get("active_sites_pdb", [])
        site_counts.append(f"PDB视角: {len(active_sites_pdb)} 个残基")
    
    total_sites = len(active_sites_uniprot or []) + len(active_sites_pdb or [])
    if total_sites == 0:
        message = f"Found enzyme '{enzyme_name}' (MCSA ID: {mcsa_id}), but no active site information is recorded."
    else:
        message = f"Successfully retrieved active site information for enzyme '{enzyme_name}' ({', '.join(site_counts)})."
    
    return ActiveSitesResponse(
        found=True,
        message=message,
        query_id=request.query_id,
        enzyme_name=enzyme_name,
        mcsa_id=mcsa_id,
        view=request.view.value,
        active_sites_uniprot=active_sites_uniprot,
        active_sites_pdb=active_sites_pdb
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
