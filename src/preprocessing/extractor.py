"""
Section Extractor for SEC Filings
Uses semantic tree structure to extract specific sections (e.g., Risk Factors)
"""

from typing import Optional, List, Dict, Union, Any
from pathlib import Path
import json
import re

from pydantic import BaseModel, ConfigDict

try:
    import sec_parser as sp
    SECPARSER_AVAILABLE = True
except ImportError:
    SECPARSER_AVAILABLE = False
    sp = None

from .parser import ParsedFiling, SECFilingParser
from .constants import SectionIdentifier, SECTION_PATTERNS, PAGE_HEADER_PATTERN, TOC_PATTERNS_COMPILED
from ..config import settings
# Import data model from models package
from .models.extraction import ExtractedSection


class SECSectionExtractor:
    """
    Extract specific sections from parsed SEC filings

    Features:
    - Section-aware extraction using semantic tree
    - Subsection identification
    - Element type preservation (text, tables, titles)
    - Metadata tracking
    - Dict-based extraction from saved JSON files

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

    Dict-based extraction example:
        >>> data = ParsedFiling.load_from_json("parsed_filing.json")
        >>> risk_section = extractor.extract_risk_factors_from_dict(data)
    """

    # Load section titles from config for maintainability
    # This allows centralized management of section identifiers
    # pylint: disable=no-member  # Pydantic dynamic config fields
    SECTION_TITLES_10K = settings.sec_sections.sections_10k
    SECTION_TITLES_10Q = settings.sec_sections.sections_10q
    # pylint: enable=no-member

    # Regex patterns imported from constants module
    # SECTION_PATTERNS = SECTION_PATTERNS  # Available via import

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
        text, subsections, elements, node_subs = self._extract_section_content(
            filing.tree, section_node, filing.form_type.value
        )
        title = self._get_section_title(section_id, filing.form_type.value)

        # Extract filing-level metadata
        filing_metadata = filing.metadata or {}

        # Build metadata — include fiscal_year/period_of_report so the segmenter
        # can promote them to SegmentedRisks.fiscal_year (Fix 6C)
        metadata = {
            'num_subsections': len(subsections),
            'num_elements': len(elements),
            'element_type_counts': self._count_element_types(elements),
            'fiscal_year': filing_metadata.get('fiscal_year'),
            'period_of_report': filing_metadata.get('period_of_report'),
            'accession_number': filing_metadata.get('accession_number'),
            'filed_as_of_date': filing_metadata.get('filed_as_of_date'),
        }

        return ExtractedSection(
            text=text,
            identifier=section_id,
            title=title,
            subsections=subsections,
            elements=elements,
            metadata=metadata,
            node_subsections=node_subs,
            # Filing-level metadata
            sic_code=filing_metadata.get('sic_code'),
            sic_name=filing_metadata.get('sic_name'),
            cik=filing_metadata.get('cik'),
            ticker=filing_metadata.get('ticker'),
            company_name=filing_metadata.get('company_name'),
            form_type=filing.form_type.value,
            accession_number=filing_metadata.get('accession_number'),
            filed_as_of_date=filing_metadata.get('filed_as_of_date'),
            period_of_report=filing_metadata.get('period_of_report'),
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

    def extract_risk_factors_from_dict(self, data: Dict[str, Any]) -> Optional[ExtractedSection]:
        """
        Extract Risk Factors section from a parsed filing dict (loaded from JSON).

        This method works with the simplified dict format saved by ParsedFiling.save_to_pickle(),
        which can be loaded via ParsedFiling.load_from_json().

        Args:
            data: Dictionary from ParsedFiling.load_from_json() with keys:
                - tree: list of node dicts with 'text', 'type', 'level'
                - form_type: "10-K" or "10-Q"
                - metadata: dict with sic_code, cik, etc.

        Returns:
            ExtractedSection with Risk Factors content, or None if not found

        Example:
            >>> data = ParsedFiling.load_from_json("parsed_filing.json")
            >>> extractor = SECSectionExtractor()
            >>> risks = extractor.extract_risk_factors_from_dict(data)
        """
        tree = data.get('tree', [])
        form_type = data.get('form_type', '10-K')
        metadata = data.get('metadata', {})

        # Find Item 1A section start
        start_idx = None
        for i, node in enumerate(tree):
            text = node.get('text', '').strip().lower()
            node_type = node.get('type', '')

            # Match "Item 1A" patterns
            if node_type in ('TopSectionTitle', 'TitleElement'):
                if re.match(r'item\s*1a[\.\s]', text) or 'risk factors' in text:
                    start_idx = i
                    break

        if start_idx is None:
            return None

        # Collect content until next section
        content_nodes = []
        subsections = []
        elements = []

        for i in range(start_idx + 1, len(tree)):
            node = tree[i]
            text = node.get('text', '').strip()
            node_type = node.get('type', '')
            lower_text = text.lower()

            # Stop at next Item section
            if node_type in ('TopSectionTitle', 'TitleElement'):
                if re.match(r'item\s*\d+[a-z]?[\.\s]', lower_text):
                    if not re.match(r'item\s*1a[\.\s]', lower_text):
                        break

            # Collect content
            if text:
                content_nodes.append(node)

                # Track subsections (TitleElement nodes)
                if node_type == 'TitleElement':
                    # Filter out page headers
                    if not PAGE_HEADER_PATTERN.match(text):
                        subsections.append(text)

                # Track all elements
                elements.append({
                    'type': node_type,
                    'text': text,
                    'level': node.get('level', 0),
                    'is_table': node_type == 'TableElement',
                })

        # Fix 6A (dict path): sequential TitleElement scan → parent_subsection map
        current_subsection: Optional[str] = None
        node_subsections_list: List[tuple] = []
        for node in content_nodes:
            if node.get('type') == 'TitleElement':
                title_text = node.get('text', '').strip()
                if title_text:
                    current_subsection = title_text
            elif (node.get('text', '').strip()
                  and node.get('type') != 'TableElement'
                  and not self._is_toc_node(node.get('text', ''))):
                node_subsections_list.append((node.get('text', '').strip(), current_subsection))

        # Build full text — exclude tables (Fix 2B) and ToC lines (Fix 2A)
        full_text = "\n\n".join([
            node.get('text', '') for node in content_nodes
            if node.get('text', '').strip()
            and node.get('type') != 'TableElement'
            and not self._is_toc_node(node.get('text', ''))
        ])

        # Include header
        header_text = tree[start_idx].get('text', '') if start_idx < len(tree) else ''
        if header_text:
            full_text = header_text + "\n\n" + full_text

        if not full_text.strip():
            return None

        section_id = 'part1item1a'
        title = self._get_section_title(section_id, form_type)

        return ExtractedSection(
            text=full_text,
            identifier=section_id,
            title=title,
            subsections=subsections,
            elements=elements,
            metadata={
                'num_subsections': len(subsections),
                'num_elements': len(elements),
                'element_type_counts': self._count_element_types(elements),
            },
            node_subsections=node_subsections_list,
            sic_code=metadata.get('sic_code'),
            sic_name=metadata.get('sic_name'),
            cik=metadata.get('cik'),
            ticker=metadata.get('ticker'),
            company_name=metadata.get('company_name'),
            form_type=form_type,
        )

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

    def _find_section_node(  # pylint: disable=too-many-branches
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
        if section_id not in SECTION_PATTERNS:
            return False

        patterns = SECTION_PATTERNS[section_id]
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
        _form_type: str
    ) -> tuple[str, List[str], List[Dict], List[tuple]]:
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
            Tuple of (full_text, subsections, elements, node_subsections)
        """
        # Convert tree.nodes to list for indexing
        all_nodes = list(tree.nodes)

        # Find the index of our section node
        try:
            start_idx = all_nodes.index(section_node)
        except ValueError:
            # Fallback to old method if node not in list
            subsections = self._extract_subsections(section_node)
            elements = self._extract_elements(section_node)
            return section_node.text, subsections, elements, []

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

            # Track subsections (TitleElement nodes), filtering out page headers
            if isinstance(node.semantic_element, sp.TitleElement):
                title_text = node.text.strip()
                # Filter out page headers (e.g., "Company | Year Form 10-K | Page")
                if not PAGE_HEADER_PATTERN.search(title_text):
                    subsections.append(title_text)

            # Track all elements
            element_dict = {
                'type': node.semantic_element.__class__.__name__,
                'text': node.text if hasattr(node, 'text') else '',
                'level': getattr(node, 'level', 0),
            }

            if isinstance(node.semantic_element, sp.TableElement):
                element_dict['is_table'] = True

            elements.append(element_dict)

        # Stage 3 (ADR-010): drop page-header TitleElements before text assembly.
        # The subsection list was already filtered above (search vs match).
        # This removes them from content_nodes so they don't appear in full_text either.
        content_nodes = [
            node for node in content_nodes
            if not (
                isinstance(node.semantic_element, sp.TitleElement)
                and PAGE_HEADER_PATTERN.search(node.text)
            )
        ]

        # Fix 6A: sequential TitleElement scan → parent_subsection map (doc order)
        current_subsection: Optional[str] = None
        node_subsections_list: List[tuple] = []
        for node in content_nodes:
            if isinstance(node.semantic_element, sp.TitleElement):
                title_text = node.text.strip()
                if title_text:
                    current_subsection = title_text
            elif (hasattr(node, 'text')
                  and node.text.strip()
                  and not isinstance(node.semantic_element, sp.TableElement)
                  and not self._is_toc_node(node.text)):
                node_subsections_list.append((node.text.strip(), current_subsection))

        # Combine all text — exclude tables (Fix 2B) and ToC lines (Fix 2A)
        full_text = "\n\n".join([
            node.text for node in content_nodes
            if hasattr(node, 'text')
            and node.text.strip()
            and not isinstance(node.semantic_element, sp.TableElement)
            and not self._is_toc_node(node.text)
        ])

        # Include the section header in the text
        if section_node.text:
            full_text = section_node.text + "\n\n" + full_text

        return full_text, subsections, elements, node_subsections_list

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
            if re.match(r'item\s+\d+[a-z]?\s*\.', text):
                return True

        return False

    def _is_toc_node(self, text: str) -> bool:
        """Return True if text looks like a Table of Contents entry (Fix 2A)."""
        text = text.strip()
        if not text:
            return False
        for pattern in TOC_PATTERNS_COMPILED:
            if pattern.search(text):
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
        return self.SECTION_TITLES_10Q.get(section_id, section_id)

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        # Remove extra whitespace, convert to lower, remove punctuation
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
                # pylint: disable=no-member  # Pydantic dynamic config
                if len(text) > settings.preprocessing.min_segment_length:
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
