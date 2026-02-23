"""
Unit tests for src/preprocessing/pre_seeker.py (Stage 1 — ADR-010).

All tests use synthetic in-memory HTML fixtures — no real filing data required.
"""

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.preprocessing.pre_seeker import AnchorPreSeeker, _decode_bytes
from src.preprocessing.models.sgml import DocumentEntry, SGMLHeader, SGMLManifest
from src.preprocessing.constants import PAGE_HEADER_PATTERN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc_entry(byte_start: int = 0, byte_end: int = 1000) -> DocumentEntry:
    return DocumentEntry(
        doc_type="10-K",
        sequence=1,
        filename="form10k.htm",
        description="Annual Report",
        byte_start=byte_start,
        byte_end=byte_end,
    )


def _make_manifest(doc_10k=None) -> SGMLManifest:
    return SGMLManifest(
        header=SGMLHeader(company_name="Test Corp"),
        documents=[],
        container_path=Path("/fake/filing.html"),
        doc_10k=doc_10k,
    )


def _write_tmp(content: bytes) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Minimal synthetic iXBRL document with ToC anchors
# ---------------------------------------------------------------------------

TOC_ITEM1A_HREF = "item1a-risks"
TOC_ITEM1B_HREF = "item1b-staff"

SYNTHETIC_DOC = f"""<!DOCTYPE html>
<html>
<head><title>Annual Report</title></head>
<body>
<!-- Table of Contents -->
<div>
  <a href="#{TOC_ITEM1A_HREF}">Item 1A. Risk Factors</a>
  <a href="#{TOC_ITEM1B_HREF}">Item 1B. Unresolved Staff Comments</a>
</div>

<!-- Body content -->
<div id="part1">
  <a id="{TOC_ITEM1A_HREF}"></a>
  <h2>Item 1A. Risk Factors</h2>
  <p>The company faces many risks including market risk and operational risk.</p>
  <p>Technology disruption is a key concern.</p>

  <a id="{TOC_ITEM1B_HREF}"></a>
  <h2>Item 1B. Unresolved Staff Comments</h2>
  <p>None.</p>
</div>
</body>
</html>
""".encode()

SYNTHETIC_DOC_NO_TOC = b"""<!DOCTYPE html>
<html>
<body>
<div>
  <p>Item 1A. Risk Factors</p>
  <p>The company faces many risks.</p>
  <p>Item 1B. Unresolved Staff Comments</p>
  <p>None.</p>
</div>
</body>
</html>
"""

SYNTHETIC_DOC_NO_ANCHORS = b"""<!DOCTYPE html>
<html>
<body>
<p>This document has no section anchors at all.</p>
<p>Random content here.</p>
</body>
</html>
"""

SYNTHETIC_DOC_MULTI_SECTION = b"""<!DOCTYPE html>
<html>
<body>
<a href="#s7">Item 7. Management Discussion</a>
<a href="#s7a">Item 7A. Quantitative Disclosures</a>

<a id="s7"></a>
<h2>Item 7. Management Discussion and Analysis</h2>
<p>Overview of financial performance.</p>
<p>Revenue increased significantly.</p>

<a id="s7a"></a>
<h2>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h2>
<p>Market risk disclosures here.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests: seek returns None when doc_10k is absent
# ---------------------------------------------------------------------------

class TestSeekGuards:
    def test_returns_none_when_doc_10k_is_none(self):
        manifest = _make_manifest(doc_10k=None)
        seeker = AnchorPreSeeker()
        result = seeker.seek(Path("/fake.html"), manifest, section_id="part1item1a")
        assert result is None

    def test_returns_none_for_unknown_section_id(self):
        """Section IDs not in SECTION_PATTERNS → target_patterns is empty → None."""
        content = SYNTHETIC_DOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="nonexistent_section_id_xyz")
        assert result is None

    def test_returns_none_when_section_not_in_ordered_list(self):
        """A valid section_id that's not in the form's ordered list → ValueError → None."""
        content = SYNTHETIC_DOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        # "part2item9" exists in SECTION_PATTERNS but not in sections_10q
        result = seeker.seek(path, manifest, section_id="part2item9", form_type="10-Q")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Strategy A — ToC href present
# ---------------------------------------------------------------------------

class TestStrategyA:
    def test_seeks_item1a_via_toc_href(self):
        content = SYNTHETIC_DOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is not None
        assert "Risk Factors" in result
        assert "The company faces many risks" in result

    def test_slice_ends_before_item1b(self):
        content = SYNTHETIC_DOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is not None
        # Item 1B content should not appear in the slice
        assert "Unresolved Staff Comments" not in result

    def test_slice_is_raw_unmodified_substring(self):
        """The returned slice must be a literal substring of the decoded doc_html."""
        content = SYNTHETIC_DOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        doc_html = content.decode("utf-8")
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is not None
        assert doc_html.find(result) != -1, "Slice must be a literal substring of doc_html"


# ---------------------------------------------------------------------------
# Tests: Strategy B — direct body scan (no ToC)
# ---------------------------------------------------------------------------

class TestStrategyB:
    def test_seeks_item1a_via_body_scan(self):
        content = SYNTHETIC_DOC_NO_TOC
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is not None
        assert "Risk Factors" in result or "many risks" in result


# ---------------------------------------------------------------------------
# Tests: no anchors → returns None
# ---------------------------------------------------------------------------

class TestNoAnchors:
    def test_returns_none_when_no_section_anchors_present(self):
        content = SYNTHETIC_DOC_NO_ANCHORS
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: case insensitivity
# ---------------------------------------------------------------------------

class TestCaseInsensitivity:
    @pytest.mark.parametrize("item_text", [
        "Item 1A. Risk Factors",
        "ITEM 1A. RISK FACTORS",
        "item 1a. risk factors",
        "Item  1A  Risk Factors",
    ])
    def test_finds_section_regardless_of_case(self, item_text: str):
        """Strategy B pattern matching must be case-insensitive."""
        doc = f"""<html><body>
<p>{item_text}</p>
<p>Detailed risk information here.</p>
<p>Item 1B. Unresolved Staff Comments</p>
</body></html>""".encode()
        path = _write_tmp(doc)
        entry = _make_doc_entry(byte_start=0, byte_end=len(doc))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part1item1a", form_type="10-K")
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: multi-section (MD&A)
# ---------------------------------------------------------------------------

class TestMultiSectionSeek:
    def test_seeks_mdna_section_with_correct_boundaries(self):
        """Seeking part2item7 should end at part2item7a, not at part1item1a."""
        content = SYNTHETIC_DOC_MULTI_SECTION
        path = _write_tmp(content)
        entry = _make_doc_entry(byte_start=0, byte_end=len(content))
        manifest = _make_manifest(doc_10k=entry)
        seeker = AnchorPreSeeker()
        result = seeker.seek(path, manifest, section_id="part2item7", form_type="10-K")
        assert result is not None
        assert "Management Discussion" in result
        assert "Revenue increased significantly" in result
        # The end anchor (Item 7A) should not be included
        assert "Market risk disclosures" not in result


# ---------------------------------------------------------------------------
# Tests: PAGE_HEADER_PATTERN variants
# ---------------------------------------------------------------------------

class TestPageHeaderPatternVariants:
    @pytest.mark.parametrize("text,should_match", [
        ("Apple Inc. | 2024 Form 10-K | 21",       True),
        ("Apple Inc. | Form 10-K | Page 21",        True),
        ("Apple Inc. | 2024 Form 10-K | Page 21",  True),
        ("Apple Inc. | Form 10-K | 21",             True),
        ("Apple Inc. | 2024 Form 10-Q | 5",        True),
        ("Apple Inc. | This is not a footer | 21", False),
        ("No pipes at all",                        False),
        ("Apple Inc. | Form 20-F | 21",            False),
    ])
    def test_page_header_pattern(self, text: str, should_match: bool):
        matched = bool(PAGE_HEADER_PATTERN.search(text))
        assert matched == should_match, (
            f"Pattern {'should' if should_match else 'should NOT'} match: {text!r}"
        )


# ---------------------------------------------------------------------------
# Tests: _decode_bytes
# ---------------------------------------------------------------------------

class TestDecodeBytes:
    def test_decodes_utf8(self):
        raw = "Hello UTF-8 \u2014".encode("utf-8")
        assert _decode_bytes(raw) == "Hello UTF-8 \u2014"

    def test_decodes_windows_1252(self):
        raw = b"Hello \x80 world"  # \x80 is € in windows-1252, control char in latin-1
        result = _decode_bytes(raw)
        assert "\u20ac" in result  # Euro sign

    def test_falls_back_to_latin1(self):
        # Byte sequence invalid in UTF-8 and windows-1252 but valid in latin-1
        raw = b"Hello \xff world"
        result = _decode_bytes(raw)
        assert "Hello" in result
        assert "world" in result
