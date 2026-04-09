"""
Sequence Info Service
Query protein sequence information from UniProt
Port: 18918
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from models import SequenceInfoQuery, SequenceInfoResponse, ErrorResponse

app = FastAPI(
    title="Sequence Info Service",
    description="Query protein sequence information (length, molecular weight, sequence) from UniProt",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fetch_uniprot_data(uniprot_id: str) -> dict:
    """Fetch protein data from UniProt REST API"""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "sequence_info"}


@app.post("/api/query/sequence-info", response_model=SequenceInfoResponse)
def query_sequence_info(request: SequenceInfoQuery):
    """
    Query protein sequence information from UniProt
    
    Returns:
        - length: Sequence length (number of amino acids)
        - molWeight: Molecular weight in Daltons
        - value: Amino acid sequence
    """
    data = fetch_uniprot_data(request.uniprot_id)
    
    if data is None:
        raise HTTPException(status_code=404, detail=f"UniProt ID {request.uniprot_id} not found")
    
    sequence = data.get("sequence", {})
    
    return SequenceInfoResponse(
        length=sequence.get("length"),
        molWeight=sequence.get("molWeight"),
        value=sequence.get("value")
    )


@app.post("/api/query/sequence-info/form", response_model=SequenceInfoResponse)
def query_sequence_info_form(uniprot_id: str):
    """Query sequence info with form parameter"""
    return query_sequence_info(SequenceInfoQuery(uniprot_id=uniprot_id))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18918)
