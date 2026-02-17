"""
Pydantic models for SEC section extraction.

Contains data structures for extracted sections from SEC filings.
"""

from typing import Optional, List, Dict, Union, Any
from pathlib import Path
import json

from pydantic import BaseModel, ConfigDict


class ExtractedSection(BaseModel):
    """
    Extracted section with metadata and structure

    Attributes:
        text: Full text content of the section
        identifier: Section identifier (e.g., "part1item1a")
        title: Human-readable section title
        subsections: List of subsection titles within this section
        elements: List of semantic elements (paragraphs, tables, etc.)
        metadata: Additional metadata about the extraction
        sic_code: Standard Industrial Classification code
        sic_name: SIC industry name (e.g., "PHARMACEUTICAL PREPARATIONS")
        cik: Central Index Key
        ticker: Stock ticker symbol
        company_name: Company name from filing
        form_type: SEC form type (10-K, 10-Q)
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )

    text: str
    identifier: str
    title: str
    subsections: List[str]
    elements: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    # Filing-level metadata (preserved through pipeline)
    sic_code: Optional[str] = None
    sic_name: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    form_type: Optional[str] = None

    def __len__(self) -> int:
        """Return character length of extracted text"""
        return len(self.text)

    def get_tables(self) -> List[Dict[str, Any]]:
        """Get all tables in this section"""
        return [el for el in self.elements if el['type'] == 'TableElement']

    def get_paragraphs(self) -> List[Dict[str, Any]]:
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

        # Convert to serializable dict using Pydantic V2
        data = {
            'version': '1.0',  # Format version for future compatibility
            **self.model_dump(),
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
            >>> path = "data/interim/extracted/AAPL_10K_risks.json"
            >>> section = ExtractedSection.load_from_json(path)
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

        # Reconstruct ExtractedSection using Pydantic V2 model_validate
        # Exclude 'version' and 'stats' which are not model fields
        model_data = {
            k: v for k, v in data.items()
            if k not in ('version', 'stats')
        }
        return ExtractedSection.model_validate(model_data)
