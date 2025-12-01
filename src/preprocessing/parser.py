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


class FormType(Enum):
    """Supported SEC form types"""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"


class ParsedFiling(BaseModel):
    """
    Parsed SEC filing with semantic structure

    Attributes:
        elements: List of semantic elements from the filing
        tree: Semantic tree structure (sections → subsections → content)
        form_type: Type of SEC form (10-K, 10-Q)
        metadata: Additional metadata about the filing
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow sec_parser types
        validate_assignment=True,
    )

    elements: List[Any]  # sp.AbstractSemanticElement - use Any for flexibility
    tree: Any  # sp.TreeNode - use Any for flexibility
    form_type: FormType
    metadata: Dict[str, Any]

    def __len__(self) -> int:
        """Return number of semantic elements"""
        return len(self.elements)

    def get_section_names(self) -> List[str]:
        """Get all top-level section names in the filing"""
        section_names = []
        if hasattr(self.tree, 'nodes'):
            for node in self.tree.nodes:
                if isinstance(node.semantic_element, sp.TopSectionTitle):
                    section_names.append(node.text.strip())
        return section_names

    def save_to_pickle(
        self,
        output_path: Union[str, Path],
        overwrite: bool = False
    ) -> Path:
        """
        Save the ParsedFiling object to a JSON file

        Note: Saves a simplified representation extracting text and metadata
        from sec-parser objects, as the full object graph cannot be pickled
        due to circular references. Uses JSON format for portability.

        Args:
            output_path: Path where the file should be saved (will use .json extension)
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            Path to the saved file

        Raises:
            FileExistsError: If file exists and overwrite=False

        Example:
            >>> filing = parser.parse_filing("AAPL_10K.html")
            >>> filing.save_to_pickle("data/interim/parsed/AAPL_10K_parsed.json")
        """
        output_path = Path(output_path)

        # Change extension to .json if it's .pkl
        if output_path.suffix == '.pkl':
            output_path = output_path.with_suffix('.json')

        # Check if file exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"File already exists: {output_path}. "
                f"Set overwrite=True to replace it."
            )

        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract serializable data
        serializable_data = self._to_serializable_dict()

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)

        return output_path

    def _to_serializable_dict(self) -> Dict:
        """
        Convert ParsedFiling to a serializable dictionary

        Extracts text and metadata from sec-parser objects which cannot
        be directly pickled due to circular references.

        Returns:
            Dictionary with serializable data
        """
        # Extract element data (text, type, etc.) with error handling
        elements_data = []
        try:
            for element in self.elements:
                try:
                    element_data = {
                        'type': element.__class__.__name__,
                        'text': str(element.text) if hasattr(element, 'text') else '',
                    }
                    # Add other simple attributes if available
                    try:
                        if hasattr(element, 'html_tag'):
                            element_data['html_tag'] = str(element.html_tag)
                    except (AttributeError, TypeError, ValueError):
                        pass
                    elements_data.append(element_data)
                except Exception as e:
                    # Skip problematic elements
                    elements_data.append({'type': 'Error', 'text': f'Error extracting: {str(e)}'})
        except Exception as e:
            print(f"Warning: Error extracting elements: {e}")

        # Extract tree structure (simplified) with error handling
        tree_data = []
        try:
            if hasattr(self.tree, 'nodes'):
                for node in self.tree.nodes:
                    try:
                        elem_type = ''
                        if hasattr(node, 'semantic_element'):
                            elem_type = node.semantic_element.__class__.__name__
                        node_data = {
                            'text': str(node.text) if hasattr(node, 'text') else '',
                            'type': elem_type,
                            'level': int(node.level) if hasattr(node, 'level') else 0,
                        }
                        tree_data.append(node_data)
                    except Exception as e:
                        # Skip problematic nodes
                        continue
        except Exception as e:
            print(f"Warning: Error extracting tree: {e}")

        # Safely get section names
        try:
            section_names = self.get_section_names()
        except Exception as e:
            print(f"Warning: Error extracting section names: {e}")
            section_names = []

        return {
            'version': '1.0',  # Format version for future compatibility
            'form_type': self.form_type.value,
            'metadata': self.metadata,
            'elements': elements_data,
            'tree': tree_data,
            'section_names': section_names,
        }

    @staticmethod
    def load_from_pickle(file_path: Union[str, Path]) -> Dict:
        """
        Load parsed filing data from a JSON file

        Note: Returns a dictionary with extracted data, not the original
        ParsedFiling object (which cannot be pickled due to circular refs).

        Args:
            file_path: Path to the JSON file (.json or .pkl extension)

        Returns:
            Dictionary containing:
                - form_type: Type of form (10-K, 10-Q)
                - metadata: Parsing metadata
                - elements: List of element dictionaries with type and text
                - tree: Simplified tree structure
                - section_names: List of section names

        Raises:
            FileNotFoundError: If file doesn't exist

        Example:
            >>> data = ParsedFiling.load_from_pickle("data/interim/parsed/AAPL_10K_parsed.json")
            >>> print(data['section_names'])
            >>> print(f"Total elements: {len(data['elements'])}")
        """
        file_path = Path(file_path)

        # Try .json extension if .pkl was specified
        if not file_path.exists() and file_path.suffix == '.pkl':
            file_path = file_path.with_suffix('.json')

        if not file_path.exists():
            raise FileNotFoundError(f"Parsed filing file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict) or 'version' not in data:
            raise ValueError(
                f"File does not contain valid parsed filing data: {file_path}"
            )

        return data


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

        # Note: sec-parser only provides Edgar10QParser, which works for all SEC forms
        # (10-K, 10-Q, 8-K, S-1, etc.) but may generate warnings for non-10-Q forms
        self.parsers = {
            FormType.FORM_10K: sp.Edgar10QParser(),
            FormType.FORM_10Q: sp.Edgar10QParser(),
        }

    def parse_filing(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        save_output: Optional[Union[str, Path, bool]] = None,
        overwrite: bool = False
    ) -> ParsedFiling:
        """
        Parse a SEC filing from HTML file

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            save_output: Optional output path for saving parsed result as pickle.
                        If True, auto-generates filename in PARSED_DATA_DIR.
                        If str/Path, saves to that specific path.
                        If None/False, doesn't save.
            overwrite: Whether to overwrite existing pickle file (default: False)

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

        # Read HTML content
        html_content = self._read_html_file(file_path)

        # Parse from content
        filing = self.parse_from_content(html_content, form_type)

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

        if form_type in ["10K", "10-K"]:
            return FormType.FORM_10K
        elif form_type in ["10Q", "10-Q"]:
            return FormType.FORM_10Q
        else:
            raise ValueError(
                f"Unsupported form type: {form_type}. "
                f"Supported types: 10-K, 10-Q"
            )

    def _extract_metadata(
        self,
        elements: List[sp.AbstractSemanticElement],
        html_content: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from parsed elements

        Args:
            elements: List of semantic elements
            html_content: Original HTML content

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

        # Extract SIC Code
        sic_code = self._extract_sic_code(html_content)

        # Extract Company Name
        company_name_match = re.search(r'COMPANY CONFORMED NAME:\s*(.+)', html_content, re.IGNORECASE)
        company_name = company_name_match.group(1).strip() if company_name_match else None

        # Extract CIK
        cik_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', html_content, re.IGNORECASE)
        cik = cik_match.group(1).strip() if cik_match else None
        
        # Determine a Ticker (heuristic, often the CIK is used by services or can be mapped)
        # For now, we'll leave Ticker as None unless explicitly found, or derive it from CIK later
        ticker = None # More complex to extract directly from HTML, usually needs CIK lookup

        return {
            'total_elements': len(elements),
            'num_sections': num_sections,
            'element_types': element_types,
            'html_size': len(html_content),
            'sic_code': sic_code,
            'company_name': company_name,
            'cik': cik,
            'ticker': ticker, # Placeholder for future ticker extraction
        }

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
            # Auto-generate filename in PARSED_DATA_DIR
            from src.config import PARSED_DATA_DIR

            # Extract filename stem and create timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{input_path.stem}_{form_type}_{timestamp}_parsed.json"
            return PARSED_DATA_DIR / filename
        else:
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
        # Remove redundant nested divs (common in SEC filings)
        # Pattern: <div><div>content</div></div> -> <div>content</div>
        import re

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
    from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, ensure_directories

    print("SEC Filing Parser with sec-parser")
    print("=" * 50)

    # Ensure directories exist
    ensure_directories()

    parser = SECFilingParser()
    info = parser.get_parser_info()

    print(f"Library: {info['library']}")
    print(f"Version: {info['version']}")
    print(f"Supported forms: {', '.join(info['supported_forms'])}")
    print(f"\nLooking for HTML files in: {RAW_DATA_DIR}")

    # Find HTML files
    html_files = list(RAW_DATA_DIR.glob("*.html"))

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

        print(f"\n--- Load from Pickle Example ---")
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
