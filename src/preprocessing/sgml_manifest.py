"""
Stage 0: SGML container manifest extraction (ADR-010).

Scans EDGAR SGML container files (.html wrappers around SGML submissions) to build
a lightweight index of embedded documents with byte offsets, plus a structured header.

Memory design: document content bytes are never loaded — only byte offsets are recorded.
The entire manifest is < 10 KB regardless of the container's total size.

Raw files in data/raw/ typically have an HTML wrapper (<!DOCTYPE html>...<body><pre>)
before the SGML content. The scanner searches for <SEC-HEADER> by byte-level scan,
not by assuming the SGML starts at byte 0.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple

from .models.sgml import DocumentEntry, SGMLHeader, SGMLManifest

# SGML spec-defined structural tags (not user-tunable; kept as module constants)
_SEC_HEADER_OPEN  = b'<SEC-HEADER>'
_SEC_HEADER_CLOSE = b'</SEC-HEADER>'
_DOCUMENT_OPEN    = b'<DOCUMENT>'
_DOCUMENT_CLOSE   = b'</DOCUMENT>'
_TEXT_OPEN        = b'<TEXT>'
_TEXT_CLOSE       = b'\n</TEXT>'

# Header field patterns (case-insensitive, strip trailing whitespace)
_HDR_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ('company_name',           re.compile(rb'COMPANY CONFORMED NAME:\s*(.+)',        re.IGNORECASE)),
    ('cik',                    re.compile(rb'CENTRAL INDEX KEY:\s*(\d+)',             re.IGNORECASE)),
    ('sic_code',               re.compile(rb'STANDARD INDUSTRIAL CLASSIFICATION:.*?\[(\d{3,4})\]',
                                          re.IGNORECASE | re.DOTALL)),
    ('sic_name',               re.compile(rb'STANDARD INDUSTRIAL CLASSIFICATION:\s*(.+?)\s*\[\d{3,4}\]',
                                          re.IGNORECASE | re.DOTALL)),
    ('period_of_report',       re.compile(rb'CONFORMED PERIOD OF REPORT[:\s]+(\d{8})', re.IGNORECASE)),
    ('accession_number',       re.compile(rb'ACCESSION NUMBER:\s*(\S+)',              re.IGNORECASE)),
    ('fiscal_year_end',        re.compile(rb'FISCAL YEAR END:\s*(\d{4})',            re.IGNORECASE)),
    ('sec_file_number',        re.compile(rb'FILE NUMBER:\s*(\S+)',                   re.IGNORECASE)),
    ('filed_as_of_date',       re.compile(rb'FILED AS OF DATE:\s*(\d{8})',            re.IGNORECASE)),
    ('document_count',         re.compile(rb'PUBLIC DOCUMENT COUNT:\s*(\d+)',         re.IGNORECASE)),
    ('state_of_incorporation', re.compile(rb'STATE OF INCORPORATION:\s*(\S+)',        re.IGNORECASE)),
    ('ein',                    re.compile(rb'IRS NUMBER:\s*(\S+)',                    re.IGNORECASE)),
]

# Document metadata line patterns (within a <DOCUMENT> block, before <TEXT>).
# EDGAR SGML uses angle-bracket tags for document-level fields: <TYPE>10-K
_DOC_TYPE_PAT        = re.compile(rb'^<TYPE>\s*(.+)',        re.IGNORECASE)
_DOC_SEQUENCE_PAT    = re.compile(rb'^<SEQUENCE>\s*(\d+)',   re.IGNORECASE)
_DOC_FILENAME_PAT    = re.compile(rb'^<FILENAME>\s*(\S+)',   re.IGNORECASE)
_DOC_DESCRIPTION_PAT = re.compile(rb'^<DESCRIPTION>\s*(.*)', re.IGNORECASE)

_CHUNK_SIZE = 64 * 1024  # 64 KB chunks for scanning document bodies


def extract_sgml_manifest(container_path: Path) -> SGMLManifest:
    """
    Build a lightweight SGMLManifest from an EDGAR SGML container file.

    Opens the file in binary mode and scans line-by-line. Document content bytes
    are never loaded into Python memory — only byte offsets are recorded.

    Args:
        container_path: Path to the SGML container (.html) file.

    Returns:
        SGMLManifest with populated header and document index.

    Raises:
        ValueError: If no <SEC-HEADER> block is found (not an SGML container).
        FileNotFoundError: If the path does not exist.
    """
    container_path = Path(container_path)
    if not container_path.exists():
        raise FileNotFoundError(f"Container not found: {container_path}")

    with open(container_path, 'rb') as f:
        raw = f.read()

    # Locate SEC-HEADER block
    hdr_start = raw.find(_SEC_HEADER_OPEN)
    if hdr_start == -1:
        raise ValueError(f"Not an SGML container (no <SEC-HEADER>): {container_path}")

    hdr_end = raw.find(_SEC_HEADER_CLOSE, hdr_start)
    if hdr_end == -1:
        hdr_end = len(raw)

    header_bytes = raw[hdr_start:hdr_end]
    header = _parse_sgml_header(header_bytes)

    # Phase 2: index all <DOCUMENT> blocks
    documents: List[DocumentEntry] = []
    doc_search_start = hdr_end

    while True:
        doc_start = raw.find(_DOCUMENT_OPEN, doc_search_start)
        if doc_start == -1:
            break

        doc_end = raw.find(_DOCUMENT_CLOSE, doc_start)
        if doc_end == -1:
            doc_end = len(raw)

        doc_block = raw[doc_start:doc_end]
        entry = _parse_document_block(doc_block, doc_start)
        if entry is not None:
            documents.append(entry)

        doc_search_start = doc_end + len(_DOCUMENT_CLOSE)

    # Phase 3: promote well-known documents
    doc_10k            = _find_10k_doc(documents)
    doc_metalinks      = _find_by_filename(documents, 'MetaLinks.json')
    doc_filing_summary = _find_by_filename(documents, 'FilingSummary.xml')
    doc_xbrl_instance  = _find_xbrl_instance(documents)

    return SGMLManifest(
        header=header,
        documents=documents,
        container_path=container_path,
        doc_10k=doc_10k,
        doc_metalinks=doc_metalinks,
        doc_filing_summary=doc_filing_summary,
        doc_xbrl_instance=doc_xbrl_instance,
    )


def extract_document(container_path: Path, entry: DocumentEntry) -> bytes:
    """
    Extract raw bytes for a single document from the SGML container.

    Uses byte-range seek so the full container is never loaded beyond what's needed.
    Strips <XBRL>...</XBRL> wrapper if present (common for inline XBRL documents).

    Args:
        container_path: Path to the SGML container file.
        entry: DocumentEntry with byte_start/byte_end offsets.

    Returns:
        Raw bytes of the document content (no SGML wrapper tags).
    """
    with open(container_path, 'rb') as f:
        f.seek(entry.byte_start)
        content = f.read(entry.byte_end - entry.byte_start)

    # Strip <XBRL>…</XBRL> wrapper if present
    stripped = content.lstrip()
    if stripped[:6].upper() == b'<XBRL>':
        xbrl_end = content.upper().rfind(b'</XBRL>')
        if xbrl_end != -1:
            inner_start = content.find(b'>') + 1  # after <XBRL>
            content = content[inner_start:xbrl_end]

    return content


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_sgml_header(header_bytes: bytes) -> SGMLHeader:
    """Parse the <SEC-HEADER> block into an SGMLHeader model."""
    fields: dict = {}

    for field_name, pattern in _HDR_PATTERNS:
        m = pattern.search(header_bytes)
        if m:
            raw_val = m.group(1).strip()
            if field_name == 'sic_name':
                # Collapse whitespace / newlines in multi-line SIC name
                raw_val = re.sub(rb'\s+', b' ', raw_val)
            if field_name == 'document_count':
                try:
                    fields[field_name] = int(raw_val)
                except ValueError:
                    pass
            elif field_name == 'fiscal_year_end':
                # EDGAR stores as MMDD (4 digits)
                fields[field_name] = raw_val.decode('latin-1', errors='replace')
            elif field_name == 'period_of_report':
                val = raw_val.decode('latin-1', errors='replace')
                fields[field_name] = val
                # Also derive fiscal_year (4-digit year prefix)
                if len(val) >= 4:
                    fields['fiscal_year'] = val[:4]
            else:
                fields[field_name] = raw_val.decode('latin-1', errors='replace')

    return SGMLHeader(**fields)


def _parse_document_block(doc_block: bytes, block_abs_start: int) -> Optional[DocumentEntry]:
    """
    Parse a single <DOCUMENT>...</DOCUMENT> block.

    Returns None if the block is malformed (missing TYPE or <TEXT> marker).
    """
    doc_type    = ''
    sequence    = 0
    filename    = ''
    description = ''

    # Scan header lines before <TEXT>
    text_marker_pos = doc_block.find(_TEXT_OPEN)
    if text_marker_pos == -1:
        return None

    preamble = doc_block[:text_marker_pos]
    for line in preamble.splitlines():
        if not doc_type:
            m = _DOC_TYPE_PAT.match(line.strip())
            if m:
                doc_type = m.group(1).strip().decode('latin-1', errors='replace')
                continue
        if not sequence:
            m = _DOC_SEQUENCE_PAT.match(line.strip())
            if m:
                try:
                    sequence = int(m.group(1))
                except ValueError:
                    pass
                continue
        if not filename:
            m = _DOC_FILENAME_PAT.match(line.strip())
            if m:
                filename = m.group(1).strip().decode('latin-1', errors='replace')
                continue
        if not description:
            m = _DOC_DESCRIPTION_PAT.match(line.strip())
            if m:
                description = m.group(1).strip().decode('latin-1', errors='replace')

    if not doc_type:
        return None

    # byte_start = absolute position just after <TEXT>\n
    text_open_abs = block_abs_start + text_marker_pos
    byte_start = text_open_abs + len(_TEXT_OPEN) + 1  # +1 for the newline

    # byte_end = absolute position of \n</TEXT>
    text_close_rel = doc_block.find(_TEXT_CLOSE, text_marker_pos)
    if text_close_rel == -1:
        # No closing </TEXT> — use end of document block
        byte_end = block_abs_start + len(doc_block)
    else:
        byte_end = block_abs_start + text_close_rel  # position of the leading \n

    return DocumentEntry(
        doc_type=doc_type,
        sequence=sequence,
        filename=filename,
        description=description,
        byte_start=byte_start,
        byte_end=byte_end,
    )


def _find_10k_doc(documents: List[DocumentEntry]) -> Optional[DocumentEntry]:
    """Promote the primary 10-K/10-K405 document (sequence 1 preferred)."""
    k10_types = {'10-K', '10-K405', '10-KSB', '10-KT'}
    candidates = [d for d in documents if d.doc_type.upper() in {t.upper() for t in k10_types}]
    if not candidates:
        return None
    # Prefer lowest sequence number
    return min(candidates, key=lambda d: d.sequence)


def _find_by_filename(documents: List[DocumentEntry], name: str) -> Optional[DocumentEntry]:
    """Find a document by exact filename (case-insensitive)."""
    name_lower = name.lower()
    for doc in documents:
        if doc.filename.lower() == name_lower:
            return doc
    return None


def _find_xbrl_instance(documents: List[DocumentEntry]) -> Optional[DocumentEntry]:
    """Find the XBRL instance document (TYPE=XML, filename ends with _htm.xml)."""
    for doc in documents:
        if doc.doc_type.upper() == 'XML' and doc.filename.lower().endswith('_htm.xml'):
            return doc
    return None
