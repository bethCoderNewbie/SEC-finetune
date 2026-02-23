"""
SEC Filing Parser using sec-parser library
Handles HTML SEC filings (10-K, 10-Q) with semantic structure preservation
"""

from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from enum import Enum
from datetime import datetime
import warnings
import json
import sys

from pydantic import BaseModel, ConfigDict

try:
    import sec_parser as sp
    from sec_parser.utils.bs4_ import approx_table_metrics
    from sec_parser.utils.bs4_.get_single_table import get_single_table
    from sec_parser.processing_engine import html_tag
    import re
    SECPARSER_AVAILABLE = True

    # Monkey patch to fix bug in sec_parser where row.find("td") returns None
    # for rows with only <th> elements, causing "'NoneType' has no attribute 'text'"
    def _fixed_get_approx_table_metrics(bs4_tag):
        """Fixed version of get_approx_table_metrics that handles missing <td> elements."""
        try:
            table = get_single_table(bs4_tag)
            # Fix: Check if td exists before accessing .text
            rows = sum(
                1 for row in table.find_all("tr")
                if (td := row.find("td")) and td.text.strip()
            )
            numbers = sum(
                bool(re.search(r"\d", cell.text))
                for cell in table.find_all("td")
                if cell.text.strip()
            )
            return approx_table_metrics.ApproxTableMetrics(rows, numbers)
        except (ValueError, TypeError, AttributeError):
            return None

    # Apply the monkey patch to all locations where the function is imported
    approx_table_metrics.get_approx_table_metrics = _fixed_get_approx_table_metrics
    html_tag.get_approx_table_metrics = _fixed_get_approx_table_metrics

except ImportError as exc:
    SECPARSER_AVAILABLE = False
    raise ImportError(
        "sec-parser is required but not installed. "
        "Install it with: pip install sec-parser"
    ) from exc

# Import data models from models package
from .models.parsing import FormType, ParsedFiling


class SECFilingParser:
    """
    Parser for SEC HTML filings using sec-parser library

    Features:
    - Semantic element extraction (titles, tables, text, etc.)
    - Tree structure preservation (sections and hierarchy)
    - Support for 10-K and 10-Q forms
    - Metadata extraction

    Example:
        >>> parser = SECFilingParser()
        >>> filing = parser.parse_filing("data/raw/AAPL_10K.html", form_type="10-K")
        >>> print(filing.get_section_names())
        ['Item 1. Business', 'Item 1A. Risk Factors', ...]
    """

    def __init__(self):
        """Initialize parser with sec-parser backends"""
        if not SECPARSER_AVAILABLE:
            raise RuntimeError("sec-parser is not available")

        # NOTE: sec-parser does not provide a dedicated Edgar10KParser.
        # Edgar10QParser is used for both forms. Section identifiers
        # (TopSectionTitle.identifier) follow 10-Q conventions — regex
        # fallback in _find_section_node handles 10-K section lookup.
        self.parsers = {
            FormType.FORM_10K: sp.Edgar10QParser(),
            FormType.FORM_10Q: sp.Edgar10QParser(),
        }

    def parse_filing(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        save_output: Optional[Union[str, Path, bool]] = None,
        overwrite: bool = False,
        recursion_limit: Optional[int] = None,
        quiet: bool = False,
        section_id: Optional[str] = None,
    ) -> ParsedFiling:
        """
        Parse a SEC filing from HTML file.

        Implements the ADR-010 3-stage pre-seek architecture:
          Stage 0: extract_sgml_manifest() → SGMLManifest (header + byte index)
          Stage 1: AnchorPreSeeker.seek()  → ~50–200 KB HTML slice
          Stage 2: Edgar10QParser.parse()  → element list (on unmodified HTML)

        Falls back to the legacy full-content path if Stage 0 fails (not an SGML
        container) or Stage 1 cannot locate anchors.

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            save_output: Optional output path for saving parsed result as pickle.
                        If True, auto-generates filename in PARSED_DATA_DIR.
                        If str/Path, saves to that specific path.
                        If None/False, doesn't save.
            overwrite: Whether to overwrite existing pickle file (default: False)
            recursion_limit: Optional recursion limit override. If None, auto-scales
                           based on file size (10000 base + 1000 per MB).
            quiet: If True, suppress warnings
            section_id: Section to pre-seek (e.g. "part1item1a"). Defaults to
                       "part1item1a". Pipeline callers pass the actual target section.

        Returns:
            ParsedFiling object with semantic structure

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is empty or invalid form type

        Example:
            >>> parser = SECFilingParser()
            >>> filing = parser.parse_filing("AAPL_10K.html", form_type="10-K", save_output=True)
            >>> print(f"Parsed {len(filing)} semantic elements")
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Filing not found: {file_path}")

        # --- Stage 0: SGML manifest ---
        manifest = None
        try:
            from .sgml_manifest import (  # pylint: disable=import-outside-toplevel
                extract_sgml_manifest, extract_document
            )
            manifest = extract_sgml_manifest(file_path)
        except (ValueError, Exception):  # noqa: BLE001  # any error → legacy fallback
            pass

        filing: ParsedFiling
        if manifest is not None and manifest.doc_10k is not None:
            # Extract full Document 1 for DEI metadata (ticker, etc.)
            full_doc1_bytes = extract_document(file_path, manifest.doc_10k)
            full_doc1_html = self._decode_bytes(full_doc1_bytes)

            # Auto-scale recursion limit on Document 1 size (not full container)
            if recursion_limit is None:
                file_size_mb = len(full_doc1_html) / (1024 * 1024)
                recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))

            # --- Stage 1: pre-seek requested section ---
            from .pre_seeker import AnchorPreSeeker  # pylint: disable=import-outside-toplevel
            fragment = AnchorPreSeeker().seek(
                file_path,
                manifest,
                section_id=section_id or "part1item1a",
                form_type=form_type,
            )

            html_for_parser = fragment if fragment is not None else full_doc1_html

            # --- Stage 2: parse fragment (Rule 1: no flatten_html before sec-parser) ---
            # quiet=True: the "10-K parsed with Edgar10QParser" warning is expected on
            # this path and fires once per file; suppress it for the internal call.
            filing = self.parse_from_content(
                html_for_parser,
                form_type,
                flatten_html=False,
                recursion_limit=recursion_limit,
                quiet=True,
            )

            # Override metadata using manifest header + full doc1 DEI
            filing.metadata = self._extract_metadata(
                filing.elements, full_doc1_html, sgml_manifest=manifest
            )

        else:
            # Legacy path: read the raw file as text and parse from content
            html_content = self._read_html_file(file_path)

            if recursion_limit is None:
                file_size_mb = len(html_content) / (1024 * 1024)
                recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))

            filing = self.parse_from_content(
                html_content, form_type,
                recursion_limit=recursion_limit,
                quiet=quiet,
            )

        # Save output if requested
        if save_output:
            output_path = self._generate_output_path(
                file_path, form_type, save_output
            )
            filing.save_to_pickle(output_path, overwrite=overwrite)
            print(f"Saved parsed filing to: {output_path}")

        return filing

    def parse_from_content(
        self,
        html_content: str,
        form_type: str = "10-K",
        recursion_limit: Optional[int] = 10000,
        flatten_html: bool = True,
        quiet: bool = False
    ) -> ParsedFiling:
        """
        Parse SEC filing from HTML content string

        Args:
            html_content: HTML content of the filing
            form_type: Type of SEC form ("10-K" or "10-Q")
            recursion_limit: Optional recursion limit for deeply nested HTML (default: 10000)
            flatten_html: If True, pre-process HTML to reduce nesting depth (improves speed)
            quiet: If True, suppress warnings

        Returns:
            ParsedFiling object with semantic structure

        Raises:
            ValueError: If content is empty or invalid form type
        """
        if not html_content or len(html_content.strip()) == 0:
            raise ValueError("HTML content is empty")

        # Pre-process HTML to flatten deep nesting (major performance optimization)
        if flatten_html:
            html_content = self._flatten_html_nesting(html_content)

        # Validate and convert form type
        form_type_enum = self._validate_form_type(form_type)

        if form_type_enum == FormType.FORM_10K and not quiet:
            warnings.warn(
                "10-K parsed with Edgar10QParser (no dedicated 10-K parser available). "
                "Section identifier matching falls back to regex patterns.",
                UserWarning,
                stacklevel=2,
            )

        # Get appropriate parser
        parser = self.parsers[form_type_enum]

        # Increase recursion limit for deeply nested HTML in SEC filings
        # Some filings have very deep nesting that exceeds Python's default limit
        original_recursion_limit = sys.getrecursionlimit()
        if recursion_limit and recursion_limit > original_recursion_limit:
            sys.setrecursionlimit(recursion_limit)
            if recursion_limit > 50000 and not quiet:
                print(f"Warning: Recursion limit set to {recursion_limit}. "
                      "This may mask issues with deeply nested HTML. "
                      "Consider reviewing the input file for excessive nesting.")

        try:
            # Parse HTML into semantic elements
            # Suppress "Invalid section type for" warning (10-K uses Edgar10QParser)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid section type for")
                elements = parser.parse(html_content)
                # Build semantic tree
                tree = sp.TreeBuilder().build(elements)
        finally:
            # Restore original recursion limit
            sys.setrecursionlimit(original_recursion_limit)

        # Extract metadata
        metadata = self._extract_metadata(elements, html_content)

        return ParsedFiling(
            elements=elements,
            tree=tree,
            form_type=form_type_enum,
            metadata=metadata
        )

    def _decode_bytes(self, raw: bytes) -> str:
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

    def _read_html_file(self, file_path: Path) -> str:
        """
        Read HTML file with proper encoding handling

        Args:
            file_path: Path to HTML file

        Returns:
            HTML content as string
        """
        try:
            # Try UTF-8 first
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Fallback to latin-1 (common in SEC filings)
            try:
                return file_path.read_text(encoding='latin-1')
            except UnicodeDecodeError:
                # Last resort: ignore errors
                return file_path.read_text(encoding='utf-8', errors='ignore')

    def _validate_form_type(self, form_type: str) -> FormType:
        """
        Validate and convert form type string to enum

        Args:
            form_type: Form type string ("10-K", "10-Q")

        Returns:
            FormType enum

        Raises:
            ValueError: If form type is not supported
        """
        form_type = form_type.upper().replace("-", "")

        if form_type == "10K":
            return FormType.FORM_10K
        if form_type == "10Q":
            return FormType.FORM_10Q
        raise ValueError(
            f"Unsupported form type: {form_type}. "
            f"Supported types: 10-K, 10-Q"
        )

    def _extract_metadata(
        self,
        elements: List[sp.AbstractSemanticElement],
        html_content: str,
        sgml_manifest: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Extract metadata from parsed elements.

        When sgml_manifest is provided (ADR-010 path), header fields are read
        directly from SGMLManifest.header instead of regex over html_content.
        html_content (always full Document 1 HTML) is still scanned for the DEI
        ticker tag, which is not present in the SGML header.

        Args:
            elements: List of semantic elements from sec-parser
            html_content: Full Document 1 HTML (used for DEI ticker regex)
            sgml_manifest: Optional SGMLManifest from Stage 0

        Returns:
            Dictionary of metadata
        """
        # Count element types
        element_types = {}
        for element in elements:
            element_type = element.__class__.__name__
            element_types[element_type] = element_types.get(element_type, 0) + 1

        # Count sections
        num_sections = sum(
            1 for el in elements
            if isinstance(el, sp.TopSectionTitle)
        )

        if sgml_manifest is not None:
            # --- ADR-010 path: use structured header fields ---
            hdr = sgml_manifest.header
            sic_code    = hdr.sic_code
            sic_name    = hdr.sic_name
            company_name = hdr.company_name
            cik          = hdr.cik
            fiscal_year  = hdr.fiscal_year
            period_of_report = hdr.period_of_report
        else:
            # --- Legacy path: regex over full HTML ---
            sic_code = self._extract_sic_code(html_content)
            sic_name = self._extract_sic_name(html_content)

            company_name_match = re.search(
                r'COMPANY CONFORMED NAME:\s*(.+)', html_content, re.IGNORECASE
            )
            company_name = company_name_match.group(1).strip() if company_name_match else None

            cik_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', html_content, re.IGNORECASE)
            cik = cik_match.group(1).strip() if cik_match else None

            period_match = re.search(
                r'CONFORMED PERIOD OF REPORT[:\s]+(\d{8})', html_content, re.IGNORECASE
            )
            fiscal_year = period_match.group(1)[:4] if period_match else None
            period_of_report = period_match.group(1) if period_match else None

        # Extract ticker from DEI inline XBRL tag (always from Document 1 HTML)
        # <ix:nonNumeric name="dei:TradingSymbol" ...>AAPL</ix:nonNumeric>
        # <ix:nonNumeric name="dei:TradingSymbol" ...><span ...>ABT</span></ix:nonNumeric>
        ticker_match = re.search(
            r'<ix:nonNumeric[^>]*name="dei:TradingSymbol"[^>]*>(.*?)</ix:nonNumeric>',
            html_content, re.IGNORECASE | re.DOTALL
        )
        if ticker_match:
            ticker = re.sub(r'<[^>]+>', '', ticker_match.group(1)).strip() or None
        else:
            ticker = None

        meta: Dict[str, Any] = {
            'total_elements': len(elements),
            'num_sections': num_sections,
            'element_types': element_types,
            'html_size': len(html_content),
            'file_size_bytes': len(html_content),  # Alias for health check validation
            'sic_code': sic_code,
            'sic_name': sic_name,
            'company_name': company_name,
            'cik': cik,
            'ticker': ticker,
            'fiscal_year': fiscal_year,
            'period_of_report': period_of_report,
        }

        # Add new fields from SGMLManifest header (ADR-010)
        if sgml_manifest is not None:
            hdr = sgml_manifest.header
            meta['accession_number']       = hdr.accession_number
            meta['filed_as_of_date']       = hdr.filed_as_of_date
            meta['fiscal_year_end']        = hdr.fiscal_year_end
            meta['sec_file_number']        = hdr.sec_file_number
            meta['document_count']         = hdr.document_count
            meta['state_of_incorporation'] = hdr.state_of_incorporation
            meta['ein']                    = hdr.ein

        return meta

    def _extract_sic_code(self, html_content: str) -> Optional[str]:
        """
        Extract SIC Code from HTML content using regex.

        Common formats:
        - STANDARD INDUSTRIAL CLASSIFICATION:  SERVICES-PREPACKAGED SOFTWARE [7372]
        - ASSIGNED-SIC: 7372
        """
        # Pattern 1: [SIC Code] inside brackets after classification name
        # e.g., STANDARD INDUSTRIAL CLASSIFICATION: ... [7372]
        pattern1 = r'STANDARD\s+INDUSTRIAL\s+CLASSIFICATION:.*?\[(\d{3,4})\]'

        # Pattern 2: ASSIGNED-SIC: 7372
        pattern2 = r'ASSIGNED-SIC:\s*(\d{3,4})'

        # Search for patterns (case-insensitive)
        match = re.search(pattern1, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)

        match = re.search(pattern2, html_content, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _extract_sic_name(self, html_content: str) -> Optional[str]:
        """
        Extract SIC Name (industry description) from HTML content using regex.

        Common format:
        - STANDARD INDUSTRIAL CLASSIFICATION:  PHARMACEUTICAL PREPARATIONS [2834]

        Returns:
            The industry name text (e.g., "PHARMACEUTICAL PREPARATIONS"), or None if not found
        """
        # Pattern to capture text between "CLASSIFICATION:" and "[code]"
        # e.g., "STANDARD INDUSTRIAL CLASSIFICATION:  PHARMACEUTICAL PREPARATIONS [2834]"
        pattern = r'STANDARD\s+INDUSTRIAL\s+CLASSIFICATION:\s*(.+?)\s*\[\d{3,4}\]'

        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            # Clean up the extracted name (remove extra whitespace, newlines)
            sic_name = match.group(1).strip()
            # Collapse multiple whitespace/newlines into single space
            sic_name = re.sub(r'\s+', ' ', sic_name)
            return sic_name

        return None

    def _generate_output_path(
        self,
        input_path: Path,
        form_type: str,
        save_output: Union[str, Path, bool]
    ) -> Path:
        """
        Generate output path for saving parsed filing

        Args:
            input_path: Path to input HTML file
            form_type: Type of SEC form
            save_output: Output path specification (True for auto-generate, or specific path)

        Returns:
            Path where the JSON file should be saved
        """
        if isinstance(save_output, bool) and save_output:
            # Auto-generate filename in parsed_data_dir
            # pylint: disable=import-outside-toplevel
            from src.config import settings as cfg
            # pylint: enable=import-outside-toplevel

            # Extract filename stem and create timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{input_path.stem}_{form_type}_{timestamp}_parsed.json"
            return cfg.paths.parsed_data_dir / filename  # pylint: disable=no-member

        # Use provided path
        path = Path(save_output)
        # Ensure .json extension
        if path.suffix == '.pkl':
            path = path.with_suffix('.json')
        return path

    def _flatten_html_nesting(self, html_content: str) -> str:
        """
        Pre-process HTML to reduce unnecessary nesting depth.
        This significantly improves parsing speed by reducing recursion.

        Args:
            html_content: Original HTML content

        Returns:
            HTML with reduced nesting depth
        """
        # Large files: regex DOTALL patterns can catastrophically backtrack on > ~10MB.
        # SEC filings commonly run 30–68MB, so delegate to the BS4-based path.
        if len(html_content) > 10 * 1024 * 1024:  # > 10MB
            return self._flatten_html_nesting_bs4(html_content)

        # Remove redundant nested divs (common in SEC filings)
        # Pattern: <div><div>content</div></div> -> <div>content</div>

        # Remove empty tags that add nesting without content
        empty_tags = ['div', 'span', 'p', 'font']
        for tag in empty_tags:
            # Remove completely empty tags: <tag></tag> or <tag />
            html_content = re.sub(
                rf'<{tag}[^>]*>\s*</{tag}>',
                '',
                html_content,
                flags=re.IGNORECASE
            )

        # Remove redundant wrapper divs (div containing only another div)
        # Do this iteratively as patterns may be nested
        for _ in range(5):  # Limit iterations to prevent infinite loops
            prev_len = len(html_content)
            # Match div that contains only whitespace and another div
            html_content = re.sub(
                r'<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>',
                r'\1',
                html_content,
                flags=re.IGNORECASE | re.DOTALL
            )
            if len(html_content) == prev_len:
                break

        # Remove redundant font tags (font containing only another font)
        for _ in range(3):
            prev_len = len(html_content)
            html_content = re.sub(
                r'<font[^>]*>\s*(<font[^>]*>.*?</font>)\s*</font>',
                r'\1',
                html_content,
                flags=re.IGNORECASE | re.DOTALL
            )
            if len(html_content) == prev_len:
                break

        # Remove excessive whitespace
        html_content = re.sub(r'\n\s*\n\s*\n', '\n\n', html_content)

        return html_content

    def _flatten_html_nesting_bs4(self, html_content: str) -> str:
        """BS4-based HTML flattening for large files (safe, no regex backtracking)."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        for tag_name in ['div', 'span', 'font']:
            for tag in soup.find_all(tag_name):
                if not tag.get_text(strip=True):
                    tag.decompose()
        return str(soup)

    def get_parser_info(self) -> Dict[str, str]:
        """
        Get information about the parser and library versions

        Returns:
            Dictionary with parser information
        """
        return {
            'library': 'sec-parser',
            'version': getattr(sp, '__version__', 'unknown'),
            'supported_forms': [ft.value for ft in FormType],
        }


def parse_filing_from_path(
    file_path: Union[str, Path],
    form_type: str = "10-K"
) -> ParsedFiling:
    """
    Convenience function to parse a SEC filing

    Args:
        file_path: Path to the HTML filing file
        form_type: Type of SEC form ("10-K" or "10-Q")

    Returns:
        ParsedFiling object

    Example:
        >>> filing = parse_filing_from_path("AAPL_10K.html")
        >>> sections = filing.get_section_names()
    """
    parser = SECFilingParser()
    return parser.parse_filing(file_path, form_type)


if __name__ == "__main__":
    # Example usage
    from src.config import settings, ensure_directories

    print("SEC Filing Parser with sec-parser")
    print("=" * 50)

    # Ensure directories exist
    ensure_directories()

    parser = SECFilingParser()
    info = parser.get_parser_info()

    print(f"Library: {info['library']}")
    print(f"Version: {info['version']}")
    print(f"Supported forms: {', '.join(info['supported_forms'])}")
    # pylint: disable=no-member
    print(f"\nLooking for HTML files in: {settings.paths.raw_data_dir}")

    # Find HTML files
    html_files = list(settings.paths.raw_data_dir.glob("*.html"))
    # pylint: enable=no-member

    if html_files:
        print(f"Found {len(html_files)} HTML file(s)")

        # Parse first file as example
        example_file = html_files[0]
        print(f"\nParsing example file: {example_file.name}")

        # Parse with auto-save enabled
        filing = parser.parse_filing(
            example_file,
            form_type="10-K",
            save_output=True  # Auto-save to PARSED_DATA_DIR
        )

        print(f"Parsed {len(filing)} semantic elements")
        print(f"Found {filing.metadata['num_sections']} sections")

        # Show section names
        sections = filing.get_section_names()
        if sections:
            print("\nTop-level sections:")
            for idx, section in enumerate(sections[:5], 1):
                print(f"  {idx}. {section}")
            if len(sections) > 5:
                print(f"  ... and {len(sections) - 5} more")

        print("\n--- Load from Pickle Example ---")
        print("To load a saved filing:")
        print("  filing = ParsedFiling.load_from_pickle('path/to/file.pkl')")
        print("\nTo inspect saved filings:")
        print("  python scripts/inspect_parsed.py list")
        print("  python scripts/inspect_parsed.py inspect <pickle_file>")

    else:
        print("No HTML files found. Add HTML files to data/raw/ to test parsing.")
        print("\nExample usage:")
        print("  parser = SECFilingParser()")
        print("  filing = parser.parse_filing('path/to/filing.html', save_output=True)")
        print("  sections = filing.get_section_names()")
        print("  filing.save_to_pickle('output.pkl')")
        print("  loaded = ParsedFiling.load_from_pickle('output.pkl')")
