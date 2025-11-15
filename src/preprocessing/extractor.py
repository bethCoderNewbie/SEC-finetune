"""
Section Extractor for SEC Filings
Uses semantic tree structure to extract specific sections (e.g., Risk Factors)
"""

from typing import Optional, List, Dict, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import re

try:
    import sec_parser as sp
    SECPARSER_AVAILABLE = True
except ImportError:
    SECPARSER_AVAILABLE = False
    sp = None

from .parser import ParsedFiling, SECFilingParser
from ..config import SEC_10K_SECTIONS, SEC_10Q_SECTIONS, EXTRACTED_DATA_DIR


class SectionIdentifier(Enum):
    """Standard section identifiers for SEC filings"""

    # 10-K Sections
    ITEM_1_BUSINESS = "part1item1"
    ITEM_1A_RISK_FACTORS = "part1item1a"
    ITEM_1B_UNRESOLVED_STAFF = "part1item1b"
    ITEM_1C_CYBERSECURITY = "part1item1c"
    ITEM_7_MDNA = "part2item7"
    ITEM_7A_MARKET_RISK = "part2item7a"
    ITEM_8_FINANCIAL_STATEMENTS = "part2item8"

    # 10-Q Sections
    ITEM_1_FINANCIAL_STATEMENTS_10Q = "part1item1"
    ITEM_2_MDNA_10Q = "part1item2"
    ITEM_1A_RISK_FACTORS_10Q = "part2item1a"


@dataclass
class ExtractedSection:
    """
    Extracted section with metadata and structure

    Attributes:
        text: Full text content of the section
        identifier: Section identifier (e.g., "part1item1a")
        title: Human-readable section title
        subsections: List of subsection titles within this section
        elements: List of semantic elements (paragraphs, tables, etc.)
        metadata: Additional metadata about the extraction
    """
    text: str
    identifier: str
    title: str
    subsections: List[str]
    elements: List[Dict]
    metadata: Dict[str, any]

    def __len__(self) -> int:
        """Return character length of extracted text"""
        return len(self.text)

    def get_tables(self) -> List[Dict]:
        """Get all tables in this section"""
        return [el for el in self.elements if el['type'] == 'TableElement']

    def get_paragraphs(self) -> List[Dict]:
        """Get all text paragraphs in this section"""
        return [el for el in self.elements if el['type'] in ['TextElement', 'ParagraphElement']]

    def save_to_json(
        self,
        output_path: Union[str, Path],
        overwrite: bool = False
    ) -> Path:
        """
        Save the ExtractedSection to a JSON file

        Args:
            output_path: Path where the file should be saved (will use .json extension)
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            Path to the saved file

        Raises:
            FileExistsError: If file exists and overwrite=False

        Example:
            >>> risk_section = extractor.extract_risk_factors(filing)
            >>> risk_section.save_to_json("data/interim/extracted/AAPL_10K_risks.json")
        """
        output_path = Path(output_path)

        # Ensure .json extension
        if output_path.suffix != '.json':
            output_path = output_path.with_suffix('.json')

        # Check if file exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"File already exists: {output_path}. "
                f"Set overwrite=True to replace it."
            )

        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable dict
        data = {
            'version': '1.0',  # Format version for future compatibility
            'text': self.text,
            'identifier': self.identifier,
            'title': self.title,
            'subsections': self.subsections,
            'elements': self.elements,
            'metadata': self.metadata,
            'stats': {
                'text_length': len(self.text),
                'num_subsections': len(self.subsections),
                'num_elements': len(self.elements),
                'num_tables': len(self.get_tables()),
                'num_paragraphs': len(self.get_paragraphs()),
            }
        }

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    @staticmethod
    def load_from_json(file_path: Union[str, Path]) -> 'ExtractedSection':
        """
        Load an ExtractedSection from a JSON file

        Args:
            file_path: Path to the JSON file

        Returns:
            ExtractedSection object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file doesn't contain valid ExtractedSection data

        Example:
            >>> section = ExtractedSection.load_from_json("data/interim/extracted/AAPL_10K_risks.json")
            >>> print(f"Loaded: {section.title}")
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict) or 'version' not in data:
            raise ValueError(
                f"File does not contain valid ExtractedSection data: {file_path}"
            )

        # Reconstruct ExtractedSection (exclude 'version' and 'stats')
        return ExtractedSection(
            text=data['text'],
            identifier=data['identifier'],
            title=data['title'],
            subsections=data['subsections'],
            elements=data['elements'],
            metadata=data['metadata']
        )


class SECSectionExtractor:
    """
    Extract specific sections from parsed SEC filings

    Features:
    - Section-aware extraction using semantic tree
    - Subsection identification
    - Element type preservation (text, tables, titles)
    - Metadata tracking

    Example:
        >>> parser = SECFilingParser()
        >>> filing = parser.parse_filing("AAPL_10K.html", form_type="10-K")
        >>>
        >>> extractor = SECSectionExtractor()
        >>> risk_section = extractor.extract_section(
        ...     filing,
        ...     SectionIdentifier.ITEM_1A_RISK_FACTORS
        ... )
        >>> print(f"Extracted {len(risk_section)} characters")
        >>> print(f"Found {len(risk_section.subsections)} risk subsections")
    """

    # Load section titles from config for maintainability
    # This allows centralized management of section identifiers
    SECTION_TITLES_10K = SEC_10K_SECTIONS
    SECTION_TITLES_10Q = SEC_10Q_SECTIONS

    # Regex patterns for flexible section matching
    # Used when identifier attribute is not set by sec-parser
    SECTION_PATTERNS = {
        "part1item1": [
            r'(?i)^item\s*1\s*\.?\s*business',
            r'(?i)^item\s*1\s*$',
            r'(?i)^item\s*1\s*[^a-z0-9]',  # Item 1 followed by non-alphanumeric
        ],
        "part1item1a": [
            r'(?i)item\s*1\s*a\.?\s*risk\s*factors?',
            r'(?i)item\s*1a\.?\s*risk',
            r'(?i)^item\s*1\s*a\s*\.?',  # Item 1A with optional period
        ],
        "part1item1b": [
            r'(?i)item\s*1\s*b\.?\s*unresolved',
            r'(?i)item\s*1b\.?',
        ],
        "part1item1c": [
            r'(?i)item\s*1\s*c\.?\s*cybersecurity',
            r'(?i)item\s*1c\.?',
        ],
        "part2item7": [
            r'(?i)item\s*7\.?\s*management',
            r'(?i)item\s*7\.?\s*md\s*&?\s*a',
            r'(?i)^item\s*7\s*\.?$',
        ],
        "part2item7a": [
            r'(?i)item\s*7\s*a\.?\s*market\s*risk',
            r'(?i)item\s*7a\.?',
        ],
    }

    def __init__(self):
        """Initialize section extractor"""
        if not SECPARSER_AVAILABLE:
            raise RuntimeError("sec-parser is required but not available")

    def extract_section(
        self,
        filing: ParsedFiling,
        section: SectionIdentifier
    ) -> Optional[ExtractedSection]:
        """
        Extract a specific section from a parsed filing

        Args:
            filing: ParsedFiling object from SECFilingParser
            section: SectionIdentifier enum specifying which section to extract

        Returns:
            ExtractedSection if found, None otherwise

        Example:
            >>> extractor = SECSectionExtractor()
            >>> risk_section = extractor.extract_section(
            ...     filing,
            ...     SectionIdentifier.ITEM_1A_RISK_FACTORS
            ... )
        """
        section_id = section.value

        # Find the section node in the tree
        section_node = self._find_section_node(filing.tree, section_id, filing.form_type.value)

        if section_node is None:
            return None

        # Extract content
        # NOTE: sec-parser creates a FLAT tree structure for sub-items
        # Content is in SIBLINGS, not DESCENDANTS
        text, subsections, elements = self._extract_section_content(
            filing.tree, section_node, filing.form_type.value
        )
        title = self._get_section_title(section_id, filing.form_type.value)

        # Build metadata
        metadata = {
            'form_type': filing.form_type.value,
            'num_subsections': len(subsections),
            'num_elements': len(elements),
            'element_type_counts': self._count_element_types(elements),
        }

        return ExtractedSection(
            text=text,
            identifier=section_id,
            title=title,
            subsections=subsections,
            elements=elements,
            metadata=metadata
        )

    def extract_risk_factors(self, filing: ParsedFiling) -> Optional[ExtractedSection]:
        """
        Convenience method to extract Risk Factors section

        Args:
            filing: ParsedFiling object

        Returns:
            ExtractedSection with Risk Factors content

        Example:
            >>> extractor = SECSectionExtractor()
            >>> risks = extractor.extract_risk_factors(filing)
            >>> print(f"Found {len(risks.subsections)} risk categories")
        """
        # Select appropriate identifier based on form type
        if filing.form_type.value == "10-K":
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS
        else:  # 10-Q
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q

        return self.extract_section(filing, section)

    def extract_mdna(self, filing: ParsedFiling) -> Optional[ExtractedSection]:
        """
        Convenience method to extract MD&A section

        Args:
            filing: ParsedFiling object

        Returns:
            ExtractedSection with MD&A content
        """
        if filing.form_type.value == "10-K":
            section = SectionIdentifier.ITEM_7_MDNA
        else:  # 10-Q
            section = SectionIdentifier.ITEM_2_MDNA_10Q

        return self.extract_section(filing, section)

    def _find_section_node(
        self,
        tree: sp.TreeNode,
        section_id: str,
        form_type: str
    ) -> Optional[sp.TreeNode]:
        """
        Find section node in the semantic tree (ENHANCED VERSION)

        Uses multiple strategies to find sections:
        1. Search TopSectionTitle nodes (for top-level items like "ITEM 1")
        2. Search TitleElement nodes (for sub-items like "ITEM 1A")
        3. Match by identifier attribute (when available)
        4. Match by regex patterns (flexible matching)
        5. Match by text normalization (fallback)

        Args:
            tree: Semantic tree from sec-parser
            section_id: Section identifier (e.g., "part1item1a")
            form_type: Form type ("10-K" or "10-Q")

        Returns:
            TreeNode if found, None otherwise
        """
        # Strategy 1: Search TopSectionTitle nodes (original approach)
        # This handles top-level sections like "ITEM 1", "PART I"
        for node in tree.nodes:
            if not isinstance(node.semantic_element, sp.TopSectionTitle):
                continue

            # Try identifier attribute first
            if hasattr(node.semantic_element, 'identifier'):
                if node.semantic_element.identifier == section_id:
                    return node

            # Try pattern matching
            if self._matches_section_pattern(node.text, section_id):
                return node

        # Strategy 2: Search TitleElement nodes (NEW - handles sub-items)
        # This is the KEY FIX: Items like "1A", "1B" are TitleElement, not TopSectionTitle
        for node in tree.nodes:
            if not isinstance(node.semantic_element, sp.TitleElement):
                continue

            # Try identifier attribute
            if hasattr(node.semantic_element, 'identifier'):
                if node.semantic_element.identifier == section_id:
                    return node

            # Try pattern matching
            if self._matches_section_pattern(node.text, section_id):
                return node

        # Strategy 3: Flexible text matching (last resort)
        expected_title = self._get_section_title(section_id, form_type)
        if expected_title:
            key_identifier = self._extract_key_identifier(expected_title)

            for node in tree.nodes:
                if not isinstance(node.semantic_element, (sp.TopSectionTitle, sp.TitleElement)):
                    continue

                node_text_normalized = self._normalize_title(node.text)

                # Check if key identifier is present and near the start
                if key_identifier and key_identifier in node_text_normalized:
                    if node_text_normalized.startswith(key_identifier) or \
                       node_text_normalized.find(key_identifier) < 20:
                        return node

        return None

    def _matches_section_pattern(self, text: str, section_id: str) -> bool:
        """
        Check if text matches any of the regex patterns for the section

        Args:
            text: Text to check
            section_id: Section identifier (e.g., "part1item1a")

        Returns:
            True if text matches any pattern for this section
        """
        if section_id not in self.SECTION_PATTERNS:
            return False

        patterns = self.SECTION_PATTERNS[section_id]
        text = text.strip()

        for pattern in patterns:
            if re.search(pattern, text):
                return True

        return False

    def _extract_key_identifier(self, title: str) -> Optional[str]:
        """
        Extract key identifier from title for flexible matching

        Examples:
            "Item 1A. Risk Factors" -> "item 1a"
            "Item 7. Management's Discussion" -> "item 7"

        Args:
            title: Section title

        Returns:
            Normalized key identifier or None
        """
        # Match patterns like "Item 1A" or "Item 7"
        match = re.search(r'item\s+\d+[a-z]?', title, re.IGNORECASE)
        if match:
            return self._normalize_title(match.group(0))
        return None

    def _extract_section_content(
        self,
        tree: sp.TreeNode,
        section_node: sp.TreeNode,
        form_type: str
    ) -> tuple[str, List[str], List[Dict]]:
        """
        Extract content from section node and its siblings (FLAT structure)

        sec-parser creates a flat tree for sub-items (like ITEM 1A):
        - The section title is one node (e.g., "ITEM 1A.")
        - Content follows as sibling nodes
        - We collect siblings until we hit the next section

        Args:
            tree: Full semantic tree
            section_node: The node marking the start of the section
            form_type: Form type ("10-K" or "10-Q")

        Returns:
            Tuple of (full_text, subsections, elements)
        """
        # Convert tree.nodes to list for indexing
        all_nodes = list(tree.nodes)

        # Find the index of our section node
        try:
            start_idx = all_nodes.index(section_node)
        except ValueError:
            # Fallback to old method if node not in list
            return section_node.text, self._extract_subsections(section_node), self._extract_elements(section_node)

        # Collect content nodes
        content_nodes = []
        subsections = []
        elements = []

        # Start from the node after the section header
        for i in range(start_idx + 1, len(all_nodes)):
            node = all_nodes[i]

            # Stop if we hit the next major section
            if self._is_next_section(node):
                break

            # Collect the node
            content_nodes.append(node)

            # Track subsections (TitleElement nodes)
            if isinstance(node.semantic_element, sp.TitleElement):
                subsections.append(node.text.strip())

            # Track all elements
            element_dict = {
                'type': node.semantic_element.__class__.__name__,
                'text': node.text if hasattr(node, 'text') else '',
                'level': getattr(node, 'level', 0),
            }

            if isinstance(node.semantic_element, sp.TableElement):
                element_dict['is_table'] = True

            elements.append(element_dict)

        # Combine all text
        full_text = "\n\n".join([
            node.text for node in content_nodes
            if hasattr(node, 'text') and node.text.strip()
        ])

        # Include the section header in the text
        if section_node.text:
            full_text = section_node.text + "\n\n" + full_text

        return full_text, subsections, elements

    def _is_next_section(self, node: sp.TreeNode) -> bool:
        """
        Check if node marks the start of a new major section

        Args:
            node: Node to check

        Returns:
            True if this node starts a new section
        """
        # Top-level sections always mark new sections
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            return True

        # TitleElement nodes that match ITEM patterns mark new sections
        if isinstance(node.semantic_element, sp.TitleElement):
            text = node.text.strip().lower()
            # Match "ITEM 1B", "ITEM 2", etc.
            if re.match(r'item\s+\d+[a-z]?\s*\.?\s*$', text):
                return True

        return False

    def _extract_subsections(self, node: sp.TreeNode) -> List[str]:
        """
        Extract subsection titles from a section node

        Args:
            node: Section node from semantic tree

        Returns:
            List of subsection titles
        """
        subsections = []

        for child in node.get_descendants():
            # TitleElement represents subsection headers
            if isinstance(child.semantic_element, sp.TitleElement):
                subsections.append(child.text.strip())

        return subsections

    def _extract_elements(self, node: sp.TreeNode) -> List[Dict]:
        """
        Extract all semantic elements from a section

        Args:
            node: Section node from semantic tree

        Returns:
            List of dictionaries with element information
        """
        elements = []

        for child in node.get_descendants():
            element_dict = {
                'type': child.semantic_element.__class__.__name__,
                'text': child.text,
                'level': getattr(child, 'level', 0),
            }

            # Add table-specific metadata
            if isinstance(child.semantic_element, sp.TableElement):
                element_dict['is_table'] = True
                # You can add table metrics here if needed

            elements.append(element_dict)

        return elements

    def _get_section_title(self, section_id: str, form_type: str) -> str:
        """Get human-readable title for section identifier"""
        if form_type == "10-K":
            return self.SECTION_TITLES_10K.get(section_id, section_id)
        else:  # 10-Q
            return self.SECTION_TITLES_10Q.get(section_id, section_id)

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        # Remove extra whitespace, convert to lower, remove punctuation
        import re
        normalized = re.sub(r'\s+', ' ', title.lower())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized.strip()

    def _count_element_types(self, elements: List[Dict]) -> Dict[str, int]:
        """Count occurrences of each element type"""
        counts = {}
        for element in elements:
            elem_type = element['type']
            counts[elem_type] = counts.get(elem_type, 0) + 1
        return counts


class RiskFactorExtractor:
    """
    Specialized extractor for Risk Factors section
    Provides backward-compatible API and additional risk-specific features

    Example:
        >>> parser = SECFilingParser()
        >>> filing = parser.parse_filing("AAPL_10K.html", form_type="10-K")
        >>>
        >>> extractor = RiskFactorExtractor()
        >>> risk_section = extractor.extract(filing)
        >>> print(f"Found {len(risk_section.subsections)} risk categories")
    """

    def __init__(self):
        """Initialize risk factor extractor"""
        self.section_extractor = SECSectionExtractor()

    def extract(self, filing: ParsedFiling) -> Optional[ExtractedSection]:
        """
        Extract Risk Factors section from filing

        Args:
            filing: ParsedFiling object from SECFilingParser

        Returns:
            ExtractedSection with Risk Factors, or None if not found
        """
        return self.section_extractor.extract_risk_factors(filing)

    def extract_from_file(
        self,
        file_path: str,
        form_type: str = "10-K"
    ) -> Optional[ExtractedSection]:
        """
        Parse file and extract Risk Factors in one step

        Args:
            file_path: Path to HTML filing
            form_type: Type of form ("10-K" or "10-Q")

        Returns:
            ExtractedSection with Risk Factors

        Example:
            >>> extractor = RiskFactorExtractor()
            >>> risks = extractor.extract_from_file("AAPL_10K.html")
            >>> print(risks.text[:500])
        """
        # Parse filing
        parser = SECFilingParser()
        filing = parser.parse_filing(file_path, form_type)

        # Extract Risk Factors
        return self.extract(filing)

    def get_risk_categories(self, section: ExtractedSection) -> List[str]:
        """
        Get list of risk category titles

        Args:
            section: ExtractedSection from extract()

        Returns:
            List of risk category names

        Example:
            >>> risks = extractor.extract(filing)
            >>> categories = extractor.get_risk_categories(risks)
            >>> print(categories)
            ['Market Risks', 'Operational Risks', 'Technology Risks', ...]
        """
        return section.subsections

    def get_risk_paragraphs(self, section: ExtractedSection) -> List[str]:
        """
        Get individual risk paragraphs as separate strings

        Args:
            section: ExtractedSection from extract()

        Returns:
            List of risk paragraph texts
        """
        paragraphs = []
        for element in section.elements:
            if element['type'] in ['TextElement', 'ParagraphElement']:
                # Filter out very short paragraphs (likely artifacts)
                text = element['text'].strip()
                if len(text) > 50:  # Minimum 50 characters
                    paragraphs.append(text)
        return paragraphs


if __name__ == "__main__":
    print("SEC Section Extractor")
    print("=" * 50)
    print("\nSupported sections:")
    print("\n10-K Sections:")
    for key, value in SECSectionExtractor.SECTION_TITLES_10K.items():
        print(f"  {key}: {value}")
    print("\n10-Q Sections:")
    for key, value in SECSectionExtractor.SECTION_TITLES_10Q.items():
        print(f"  {key}: {value}")
