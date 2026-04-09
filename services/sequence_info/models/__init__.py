"""Sequence Info Service Models"""

from pydantic import BaseModel, Field
from typing import Optional


class SequenceInfoQuery(BaseModel):
    """Query model for sequence information"""
    uniprot_id: str = Field(..., description="UniProt ID (e.g., P12345)")


class SequenceInfoResponse(BaseModel):
    """Response model for sequence information"""
    length: Optional[int] = Field(None, description="Sequence length")
    molWeight: Optional[int] = Field(None, description="Molecular weight in Daltons")
    value: Optional[str] = Field(None, description="Amino acid sequence")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
