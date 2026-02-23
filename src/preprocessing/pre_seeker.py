"""
Stage 1: Anchor pre-seeker for EDGAR iXBRL documents (ADR-010).

Locates the HTML slice for a requested section (e.g., Item 1A Risk Factors)
within Document 1 of an EDGAR filing to avoid parsing the full 5–10 MB body.

Performance design
------------------
BeautifulSoup(lxml) on a full 5–10 MB document costs 0.5–1.5 s and creates a
large heap allocation. Using SoupStrainer forces the C-level lxml parser to build
Python objects **only for the targeted tag type**, ignoring the bulk of the
document at the C level.

Two strategies are attempted in order:
  A. SoupStrainer("a")           — ToC <a href="#..."> → body <a id="..."> resolution
  B. SoupStrainer(["span","div","p"]) — direct text-proximity scan (ToC-less filings)

If both strategies fail, None is returned and the caller falls back to passing the
full Document 1 HTML to sec-parser (Rule 7 of ADR-010).

Expected fallback rate: ~5 % of corpus.
"""

import re
from pathlib import Path
from typing import Optional

from .sgml_manifest import extract_document
from .models.sgml import SGMLManifest
from .constants import SECTION_PATTERNS


class AnchorPreSeeker:
    """
    Seeks the HTML slice for a requested section within an EDGAR iXBRL document.

    Reads section ordering from ``settings.sec_sections`` at init time so that
    end-anchor detection uses document order, not hardcoded Item numbers.
    """

    def __init__(self):
        from src.config import settings  # pylint: disable=import-outside-toplevel
        self._sections_10k: dict = settings.sec_sections.sections_10k  # pylint: disable=no-member
        self._sections_10q: dict = settings.sec_sections.sections_10q  # pylint: disable=no-member

    def seek(
        self,
        container_path: Path,
        manifest: SGMLManifest,
        section_id: str = "part1item1a",
        form_type: str = "10-K",
    ) -> Optional[str]:
        """
        Extract the HTML slice for *section_id* from Document 1 of the filing.

        Args:
            container_path: Path to the SGML container file (for extract_document).
            manifest:        SGMLManifest produced by extract_sgml_manifest().
            section_id:      Section identifier key (e.g. ``"part1item1a"``).
            form_type:       ``"10-K"`` or ``"10-Q"``.

        Returns:
            Raw, unmodified HTML substring ``doc_html[start:end]``, or ``None``
            if neither strategy locates the section.
        """
        if manifest.doc_10k is None:
            return None

        # Determine target and end patterns from config-ordered section list
        target_patterns = [re.compile(p) for p in SECTION_PATTERNS.get(section_id, [])]
        if not target_patterns:
            return None

        sections = self._sections_10k if form_type == "10-K" else self._sections_10q
        ordered = list(sections.keys())
        try:
            idx = ordered.index(section_id)
        except ValueError:
            return None

        end_section_ids = ordered[idx + 1:]
        end_patterns = [
            re.compile(p)
            for sid in end_section_ids
            for p in SECTION_PATTERNS.get(sid, [])
        ]

        # Load Document 1 and decode
        doc_bytes = extract_document(container_path, manifest.doc_10k)
        doc_html = _decode_bytes(doc_bytes)

        # Strategy A: ToC <a href="..."> → body <a id="...">
        result = self._strategy_a(doc_html, target_patterns, end_patterns)
        if result is not None:
            return result

        # Strategy B: direct text-proximity scan
        return self._strategy_b(doc_html, target_patterns, end_patterns)

    # ------------------------------------------------------------------
    # Strategy A: Table of Contents anchor resolution
    # ------------------------------------------------------------------

    def _strategy_a(
        self,
        doc_html: str,
        target_patterns: list,
        end_patterns: list,
    ) -> Optional[str]:
        """
        Use SoupStrainer("a") to locate ToC href → body id anchor chain.

        lxml ignores all non-<a> nodes at the C level when SoupStrainer("a") is used,
        keeping this step under ~50 ms even on 10 MB documents.
        """
        try:
            from bs4 import BeautifulSoup, SoupStrainer  # pylint: disable=import-outside-toplevel
        except ImportError:
            return None

        only_anchors = SoupStrainer("a")
        soup = BeautifulSoup(doc_html, "lxml", parse_only=only_anchors)

        # Find ToC anchor: <a href="#fragment_id"> whose text matches target
        toc_anchor = None
        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "")
            if not href.startswith("#"):
                continue
            text = tag.get_text(separator=" ", strip=True)
            if any(p.search(text) for p in target_patterns):
                toc_anchor = tag
                break

        if toc_anchor is None:
            return None

        fragment_id = toc_anchor["href"][1:]  # strip leading "#"

        # Locate the body anchor <a id="fragment_id"> (or <a name="...">)
        start_pos = _find_anchor_pos(doc_html, fragment_id)
        if start_pos == -1:
            return None

        # Locate end anchor
        end_pos = _find_end_pos(doc_html, start_pos + 1, end_patterns, soup)
        if end_pos == -1:
            end_pos = len(doc_html)

        return doc_html[start_pos:end_pos]

    # ------------------------------------------------------------------
    # Strategy B: Direct text-proximity scan
    # ------------------------------------------------------------------

    def _strategy_b(
        self,
        doc_html: str,
        target_patterns: list,
        end_patterns: list,
    ) -> Optional[str]:
        """
        Direct regex scan of the raw HTML for section boundaries.

        Fallback when ToC anchor resolution fails (ToC-less or non-standard filings).

        Scans doc_html directly with the compiled target/end patterns. This avoids
        the BS4 round-trip problem where str(tag) != raw source (entity encoding,
        attribute ordering). EDGAR section headings are plain ASCII so the patterns
        reliably match the raw text.
        """
        # Find start: first target-pattern match in raw HTML
        start_match = None
        for pattern in target_patterns:
            m = pattern.search(doc_html)
            if m and (start_match is None or m.start() < start_match.start()):
                start_match = m

        if start_match is None:
            return None

        # Walk back to the opening < of the surrounding tag
        start_pos = doc_html.rfind('<', 0, start_match.start())
        if start_pos == -1:
            start_pos = start_match.start()

        # Find end: first end-pattern match after start_pos
        end_pos = len(doc_html)
        for pattern in end_patterns:
            m = pattern.search(doc_html, start_pos + 1)
            if m:
                candidate = doc_html.rfind('<', 0, m.start())
                if candidate == -1:
                    candidate = m.start()
                if candidate > start_pos and candidate < end_pos:
                    end_pos = candidate

        return doc_html[start_pos:end_pos]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _decode_bytes(raw: bytes) -> str:
    """
    Decode bytes from an EDGAR document with proper encoding fallback chain.

    Older EDGAR filings frequently use windows-1252 (not latin-1).
    latin-1 is a last resort: it never throws but may produce mojibake
    for the 0x80–0x9F range (windows-1252 printable chars).
    """
    for encoding in ('utf-8', 'windows-1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1')  # always succeeds; may produce mojibake in 0x80-0x9F range


def _find_anchor_pos(doc_html: str, fragment_id: str) -> int:
    """
    Locate the character position of any element with id="fragment_id" in doc_html.

    Modern EDGAR iXBRL filings use ``<div id="...">`` (not ``<a id="...">``).
    This function matches any tag type, not just ``<a>``.
    Returns -1 if not found.
    """
    pattern = re.compile(
        r'\bid\s*=\s*"' + re.escape(fragment_id) + r'"',
        re.IGNORECASE,
    )
    m = pattern.search(doc_html)
    if m is None:
        return -1
    # Back up to the opening < of the tag that contains this id attribute
    tag_start = doc_html.rfind('<', 0, m.start())
    return tag_start if tag_start != -1 else m.start()


def _find_end_pos(
    doc_html: str,
    search_from: int,
    end_patterns: list,
    anchor_soup,
) -> int:
    """
    Find the earliest end-section anchor position after search_from.

    Strategy: scan all ToC href anchors in anchor_soup; for each whose text matches
    end_patterns, resolve the body anchor via _find_anchor_pos (any element id=).
    Falls back to plain regex scan on raw HTML if no ToC match found.
    """
    best = -1

    # Try ToC href anchors from the pre-parsed anchor soup
    for tag in anchor_soup.find_all("a", href=True):
        href = tag.get("href", "")
        if not href.startswith("#"):
            continue
        toc_text = tag.get_text(separator=" ", strip=True)
        if not any(p.search(toc_text) for p in end_patterns):
            continue
        fragment_id = href[1:]
        pos = _find_anchor_pos(doc_html, fragment_id)
        if pos != -1 and pos > search_from:
            if best == -1 or pos < best:
                best = pos

    if best != -1:
        return best

    # Fallback: regex scan for end-pattern text in the remaining HTML
    remaining = doc_html[search_from:]
    for pattern in end_patterns:
        m = pattern.search(remaining)
        if m:
            candidate = search_from + m.start()
            if best == -1 or candidate < best:
                best = candidate

    return best


def _find_text_pos_in_html(doc_html: str, tags, patterns: list, min_pos: int) -> int:
    """
    Find the first position in doc_html (>= min_pos) where an element's plain text
    matches any of patterns.

    Uses the tag's get_text() result to build a short unique search key, then
    locates that key in the raw HTML with re.search (handles entity-encoding and
    whitespace differences between BS4 output and raw source).

    Returns the position of the opening < of the matched tag, or -1.
    """
    for tag in tags:
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue
        if not any(p.search(text) for p in patterns):
            continue

        # Build a search key: first ~40 chars of plain text, stripped of leading
        # punctuation, to anchor-search in the raw HTML.
        # We can't use str(tag) because BS4 normalises entities & attribute order.
        key = text[:40].strip()
        if not key:
            continue
        # Escape for regex; allow flexible whitespace between words (handles &nbsp;)
        words = key.split()
        if not words:
            continue
        # Use the first 3 words joined by a lenient whitespace pattern
        needle = r'\s+'.join(re.escape(w) for w in words[:3])
        m = re.search(needle, doc_html[min_pos:], re.IGNORECASE)
        if m is None:
            continue
        abs_pos = min_pos + m.start()
        # Walk back to the opening < of the containing tag
        tag_start = doc_html.rfind('<', 0, abs_pos)
        if tag_start == -1:
            tag_start = abs_pos
        return tag_start

    return -1
