"""
Pydantic models for SGML container manifest (Stage 0 of ADR-010 pipeline).

These models represent the structured metadata extracted from the EDGAR SGML
container without loading document content into memory.
"""

from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class DocumentEntry(BaseModel):
    """Byte-indexed entry for a single embedded document within an SGML container."""
    model_config = ConfigDict(validate_assignment=True)

    doc_type:    str
    sequence:    int
    filename:    str
    description: str
    byte_start:  int   # byte position after <TEXT>\n
    byte_end:    int   # byte position of \n</TEXT>


class SGMLHeader(BaseModel):
    """
    Structured metadata from the <SEC-HEADER> block of an EDGAR SGML container.

    Covers all 14 standard EDGAR header fields. The first 6 were previously
    extracted via regex; the remaining 8 are new (ADR-010).
    """
    model_config = ConfigDict(validate_assignment=True)

    # Original 6 fields
    company_name:     Optional[str] = None
    cik:              Optional[str] = None
    sic_code:         Optional[str] = None
    sic_name:         Optional[str] = None
    fiscal_year:      Optional[str] = None   # 4-digit year from CONFORMED PERIOD OF REPORT
    period_of_report: Optional[str] = None   # YYYYMMDD from CONFORMED PERIOD OF REPORT

    # New 8 fields (ADR-010)
    accession_number:       Optional[str] = None   # e.g. "0000320193-21-000105"
    fiscal_year_end:        Optional[str] = None   # MMDD, e.g. "0924"
    sec_file_number:        Optional[str] = None   # e.g. "001-36743"
    filed_as_of_date:       Optional[str] = None   # YYYYMMDD
    document_count:         Optional[int] = None
    state_of_incorporation: Optional[str] = None   # 2-letter state code
    ein:                    Optional[str] = None   # IRS Employer Identification Number


class SGMLManifest(BaseModel):
    """
    Complete manifest of an EDGAR SGML container file.

    Carries the structured header and a byte-level index of all embedded
    documents. The container_path is required alongside byte offsets because
    offsets are only valid for that specific file.
    """
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    header:             SGMLHeader
    documents:          List[DocumentEntry] = Field(default_factory=list)
    container_path:     Path                           # required — byte offsets are file-specific
    doc_10k:            Optional[DocumentEntry] = None
    doc_metalinks:      Optional[DocumentEntry] = None
    doc_filing_summary: Optional[DocumentEntry] = None
    doc_xbrl_instance:  Optional[DocumentEntry] = None
