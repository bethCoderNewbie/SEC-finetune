"""
SEC Filing Parser using sec-parser library
Handles HTML SEC filings (10-K, 10-Q) with semantic structure preservation
"""

from pathlib import Path
from typing import List, Optional, Union, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import warnings
import json
import sys

try:
    import sec_parser as sp
    SECPARSER_AVAILABLE = True
except ImportError:
    SECPARSER_AVAILABLE = False
    raise ImportError(
        "sec-parser is required but not installed. "
        "Install it with: pip install sec-parser"
    )


class FormType(Enum):
    """Supported SEC form types"""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"


@dataclass
class ParsedFiling:
    """
    Parsed SEC filing with semantic structure

    Attributes:
        elements: List of semantic elements from the filing
        tree: Semantic tree structure (sections → subsections → content)
        form_type: Type of SEC form (10-K, 10-Q)
        metadata: Additional metadata about the filing
    """
    elements: List[sp.AbstractSemanticElement]
    tree: sp.TreeNode
    form_type: FormType
    metadata: Dict[str, any]

    def __len__(self) -> int:
        """Return number of semantic elements"""
        return len(self.elements)

    def get_section_names(self) -> List[str]:
        """Get all top-level section names in the filing"""
        sections = []
        for node in self.tree.nodes:
            if isinstance(node.semantic_element, sp.TopSectionTitle):
                sections.append(node.text.strip())
        return sections

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
                    except:
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
                        node_data = {
                            'text': str(node.text) if hasattr(node, 'text') else '',
                            'type': node.semantic_element.__class__.__name__ if hasattr(node, 'semantic_element') else '',
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
        form_type: str = "10-K"
    ) -> ParsedFiling:
        """
        Parse SEC filing from HTML content string

        Args:
            html_content: HTML content of the filing
            form_type: Type of SEC form ("10-K" or "10-Q")

        Returns:
            ParsedFiling object with semantic structure

        Raises:
            ValueError: If content is empty or invalid form type
        """
        if not html_content or len(html_content.strip()) == 0:
            raise ValueError("HTML content is empty")

        # Validate and convert form type
        form_type_enum = self._validate_form_type(form_type)

        # Get appropriate parser
        parser = self.parsers[form_type_enum]

        # Parse HTML into semantic elements
        # Suppress warnings for non-10-Q forms (10-K uses Edgar10QParser but generates warnings)
        if form_type_enum == FormType.FORM_10K:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid section type for")
                elements = parser.parse(html_content)
        else:
            elements = parser.parse(html_content)

        # Build semantic tree
        tree = sp.TreeBuilder().build(elements)

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
    ) -> Dict[str, any]:
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

        return {
            'total_elements': len(elements),
            'num_sections': num_sections,
            'element_types': element_types,
            'html_size': len(html_content),
        }

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
