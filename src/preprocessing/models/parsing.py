"""
Pydantic models for SEC filing parsing.

Contains data structures for parsed SEC filings (10-K, 10-Q).
"""

from pathlib import Path
from typing import List, Union, Dict, Any
from enum import Enum
import json

from pydantic import BaseModel, ConfigDict

try:
    import sec_parser as sp
    SECPARSER_AVAILABLE = True
except ImportError:
    SECPARSER_AVAILABLE = False


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
        if SECPARSER_AVAILABLE and hasattr(self.tree, 'nodes'):
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
                except (AttributeError, TypeError, ValueError) as e:
                    # Skip problematic elements
                    elements_data.append({'type': 'Error', 'text': f'Error extracting: {str(e)}'})
        except (AttributeError, TypeError) as e:
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
                    except (AttributeError, TypeError, ValueError):
                        # Skip problematic nodes
                        continue
        except (AttributeError, TypeError) as e:
            print(f"Warning: Error extracting tree: {e}")

        # Safely get section names
        try:
            section_names = self.get_section_names()
        except (AttributeError, TypeError) as e:
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
    def load_from_json(file_path: Union[str, Path]) -> Dict:
        """
        Load parsed filing data from a JSON file

        Alias for load_from_pickle() - both load JSON format.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dictionary with parsed filing data

        Example:
            >>> data = ParsedFiling.load_from_json("path/to/file.json")
            >>> print(data['section_names'])
        """
        return ParsedFiling.load_from_pickle(file_path)

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
