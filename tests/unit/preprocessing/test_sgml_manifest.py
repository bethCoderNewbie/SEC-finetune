"""
Unit tests for src/preprocessing/sgml_manifest.py (Stage 0 — ADR-010).

All tests use synthetic in-memory SGML fixtures — no real filing data required.
"""

import io
import tempfile
from pathlib import Path

import pytest

from src.preprocessing.sgml_manifest import extract_sgml_manifest, extract_document
from src.preprocessing.models.sgml import DocumentEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_sgml_container(
    header_extra: str = "",
    docs: list = None,
) -> bytes:
    """
    Build a minimal synthetic SGML container as bytes.

    Args:
        header_extra: Additional header lines to inject between <SEC-HEADER> tags.
        docs: List of dicts with keys: type, sequence, filename, description, content.
    """
    if docs is None:
        docs = []

    header = (
        b"<SEC-HEADER>\n"
        b"COMPANY CONFORMED NAME:  ACME CORP\n"
        b"CENTRAL INDEX KEY:       0000123456\n"
        b"STANDARD INDUSTRIAL CLASSIFICATION: COMPUTER HARDWARE [3577]\n"
        b"CONFORMED PERIOD OF REPORT: 20211231\n"
        b"ACCESSION NUMBER: 0000123456-21-000999\n"
        b"FILED AS OF DATE: 20220215\n"
        b"PUBLIC DOCUMENT COUNT: 3\n"
        b"STATE OF INCORPORATION: DE\n"
        b"IRS NUMBER: 123456789\n"
        + header_extra.encode()
        + b"\n</SEC-HEADER>\n"
    )

    document_blocks = b""
    for doc in docs:
        content_bytes = doc.get("content", b"<html>test</html>")
        block = (
            b"<DOCUMENT>\n"
            b"<TYPE>" + doc.get("type", "10-K").encode() + b"\n"
            b"<SEQUENCE>" + str(doc.get("sequence", 1)).encode() + b"\n"
            b"<FILENAME>" + doc.get("filename", "doc.htm").encode() + b"\n"
            b"<DESCRIPTION>" + doc.get("description", "").encode() + b"\n"
            b"<TEXT>\n"
            + content_bytes
            + b"\n</TEXT>\n"
            b"</DOCUMENT>\n"
        )
        document_blocks += block

    return header + document_blocks


def _write_tmp(content: bytes) -> Path:
    """Write bytes to a temporary file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Tests: header extraction
# ---------------------------------------------------------------------------

class TestExtractSgmlHeader:
    def test_extracts_company_name(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.company_name == "ACME CORP"

    def test_extracts_cik(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.cik == "0000123456"

    def test_extracts_accession_number(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.accession_number == "0000123456-21-000999"

    def test_extracts_filed_as_of_date(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.filed_as_of_date == "20220215"

    def test_extracts_period_of_report_and_fiscal_year(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.period_of_report == "20211231"
        assert manifest.header.fiscal_year == "2021"

    def test_extracts_sic_code_and_name(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.sic_code == "3577"
        assert manifest.header.sic_name == "COMPUTER HARDWARE"

    def test_extracts_document_count(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.document_count == 3

    def test_extracts_state_of_incorporation(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.state_of_incorporation == "DE"

    def test_extracts_ein(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.header.ein == "123456789"


# ---------------------------------------------------------------------------
# Tests: document index
# ---------------------------------------------------------------------------

class TestBuildDocumentIndex:
    def test_builds_two_document_entries(self):
        raw = _make_sgml_container(docs=[
            {"type": "10-K",    "sequence": 1, "filename": "filing.htm",   "content": b"<html>doc1</html>"},
            {"type": "EX-31.1", "sequence": 2, "filename": "exhibit.htm",  "content": b"<html>doc2</html>"},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert len(manifest.documents) == 2
        assert manifest.documents[0].doc_type == "10-K"
        assert manifest.documents[1].doc_type == "EX-31.1"

    def test_byte_offsets_are_positive(self):
        content = b"<html>body of document one</html>"
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "f.htm", "content": content},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert len(manifest.documents) == 1
        entry = manifest.documents[0]
        assert entry.byte_start >= 0
        assert entry.byte_end > entry.byte_start

    def test_byte_start_end_span_correct_content(self):
        content = b"<html>unique-marker-xyz</html>"
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "f.htm", "content": content},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        entry = manifest.documents[0]
        with open(path, "rb") as f:
            f.seek(entry.byte_start)
            extracted = f.read(entry.byte_end - entry.byte_start)
        assert b"unique-marker-xyz" in extracted


# ---------------------------------------------------------------------------
# Tests: document promotion
# ---------------------------------------------------------------------------

class TestPromoteDocuments:
    def test_promotes_doc_10k(self):
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "form10k.htm", "content": b"<html/>"},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.doc_10k is not None
        assert manifest.doc_10k.doc_type == "10-K"

    def test_doc_10k_is_none_when_absent(self):
        raw = _make_sgml_container(docs=[
            {"type": "EX-21", "sequence": 1, "filename": "subs.htm", "content": b"<html/>"},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.doc_10k is None

    def test_promotes_metalinks(self):
        raw = _make_sgml_container(docs=[
            {"type": "10-K",       "sequence": 1, "filename": "form10k.htm",  "content": b"<html/>"},
            {"type": "JSON",       "sequence": 88, "filename": "MetaLinks.json", "content": b"{}"},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.doc_metalinks is not None
        assert manifest.doc_metalinks.filename == "MetaLinks.json"

    def test_promotes_filing_summary(self):
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "form10k.htm",       "content": b"<html/>"},
            {"type": "XML",  "sequence": 2, "filename": "FilingSummary.xml", "content": b"<xml/>"},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.doc_filing_summary is not None
        assert manifest.doc_filing_summary.filename == "FilingSummary.xml"


# ---------------------------------------------------------------------------
# Tests: extract_document
# ---------------------------------------------------------------------------

class TestExtractDocument:
    def test_returns_correct_byte_slice(self):
        content = b"<html>risk factors content here</html>"
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "f.htm", "content": content},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        result = extract_document(path, manifest.doc_10k)
        assert b"risk factors content here" in result

    def test_strips_xbrl_wrapper(self):
        inner = b"<html><body>actual content</body></html>"
        content = b"<XBRL>\n" + inner + b"\n</XBRL>"
        raw = _make_sgml_container(docs=[
            {"type": "10-K", "sequence": 1, "filename": "f.htm", "content": content},
        ])
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        result = extract_document(path, manifest.doc_10k)
        assert b"actual content" in result
        assert b"<XBRL>" not in result.upper()


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_non_sgml_file_raises_value_error(self):
        """A plain HTML file with no <SEC-HEADER> must raise ValueError."""
        plain_html = b"<!DOCTYPE html><html><body><p>Hello</p></body></html>"
        path = _write_tmp(plain_html)
        with pytest.raises(ValueError, match="Not an SGML container"):
            extract_sgml_manifest(path)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_sgml_manifest(Path("/nonexistent/path/filing.html"))

    def test_container_path_stored_on_manifest(self):
        raw = _make_sgml_container()
        path = _write_tmp(raw)
        manifest = extract_sgml_manifest(path)
        assert manifest.container_path == path
