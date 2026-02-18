"""
Pydantic models for risk factor segmentation.

Contains data structures for individual risk segments and segmented risk collections.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, ConfigDict


class RiskSegment(BaseModel):
    """Individual risk segment with index"""
    model_config = ConfigDict(validate_assignment=True)

    index: int
    text: str
    word_count: int = 0
    char_count: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        if self.word_count == 0:
            self.word_count = len(self.text.split())
        if self.char_count == 0:
            self.char_count = len(self.text)


class SegmentedRisks(BaseModel):
    """
    Segmented risk factors with preserved metadata

    Attributes:
        segments: List of individual risk segments
        sic_code: Standard Industrial Classification code
        sic_name: SIC industry name (e.g., "PHARMACEUTICAL PREPARATIONS")
        cik: Central Index Key
        ticker: Stock ticker symbol
        company_name: Company name from filing
        form_type: SEC form type (10-K, 10-Q)
        section_title: Original section title
        total_segments: Number of segments
        metadata: Additional metadata
    """
    model_config = ConfigDict(validate_assignment=True)

    segments: List[RiskSegment]
    sic_code: Optional[str] = None
    sic_name: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    form_type: Optional[str] = None
    section_title: Optional[str] = None
    total_segments: int = 0
    metadata: Dict[str, Any] = {}

    def __init__(self, **data):
        super().__init__(**data)
        if self.total_segments == 0:
            self.total_segments = len(self.segments)

    def __len__(self) -> int:
        return len(self.segments)

    def get_texts(self) -> List[str]:
        """Get all segment texts as a list"""
        return [seg.text for seg in self.segments]

    def save_to_json(
        self,
        output_path: Union[str, Path],
        overwrite: bool = False
    ) -> Path:
        """
        Save segmented risks to JSON file

        Args:
            output_path: Path to save the JSON file
            overwrite: Whether to overwrite existing file

        Returns:
            Path to saved file
        """
        output_path = Path(output_path)

        if output_path.suffix != '.json':
            output_path = output_path.with_suffix('.json')

        if output_path.exists() and not overwrite:
            raise FileExistsError(f"File exists: {output_path}. Set overwrite=True.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Derive filing_name from output path (strip _segmented suffix added by pipeline)
        filing_name = output_path.stem.removesuffix('_segmented')

        data = {
            'version': '1.0',
            'filing_name': filing_name,
            'num_segments': self.total_segments,
            **self.model_dump(),
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    @staticmethod
    def load_from_json(file_path: Union[str, Path]) -> 'SegmentedRisks':
        """Load segmented risks from JSON file"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'version' in data:
            del data['version']

        return SegmentedRisks.model_validate(data)
