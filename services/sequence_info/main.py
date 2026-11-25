"""
Sequence Info Service
Query protein sequence information from UniProt
Port: 18918
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import sys
from pathlib import Path
from models import SequenceInfoQuery, SequenceInfoResponse, ErrorResponse

root = str(Path(__file__).resolve().parents[2])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.sequence_mass import sequence_mass
from shared.uniprot import uniprot_json_client, UniProtDownloadError

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
    """Preserve the existing lookup contract using the verified shared client."""
    try:
        return uniprot_json_client.fetch_json(uniprot_id, capability='sequence')
    except UniProtDownloadError as exc:
        if exc.code == 'uniprot_not_found':
            return None
        raise


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
    try:
        data = fetch_uniprot_data(request.uniprot_id)
    except UniProtDownloadError as exc:
        status = 422 if exc.code == 'uniprot_invalid_accession' else 502
        raise HTTPException(status_code=status, detail=str(exc)) from None
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="UniProt sequence lookup timed out. Please retry.") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="UniProt sequence data are temporarily unavailable.") from None
    
    if data is None:
        raise HTTPException(status_code=404, detail=f"UniProt ID {request.uniprot_id} not found")
    
    sequence = data.get("sequence", {})
    
    mass, mass_source, note = sequence_mass(sequence)
    return SequenceInfoResponse(
        length=sequence.get("length"),
        molWeight=mass, molWeight_source=mass_source, molWeight_note=note,
        value=sequence.get("value"),
        source=data.get("enzymindSource")
    )


@app.post("/api/query/sequence-info/form", response_model=SequenceInfoResponse)
def query_sequence_info_form(uniprot_id: str):
    """Query sequence info with form parameter"""
    return query_sequence_info(SequenceInfoQuery(uniprot_id=uniprot_id))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18918)
