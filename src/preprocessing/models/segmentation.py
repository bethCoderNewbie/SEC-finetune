"""
Pydantic models for risk factor segmentation.

Contains data structures for individual risk segments and segmented risk collections.
"""

import re
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, ConfigDict


class RiskSegment(BaseModel):
    """Individual risk segment with structured chunk identifier (Fix 6B)"""
    model_config = ConfigDict(validate_assignment=True)

    chunk_id: str                           # "1A_001", "1A_002", … (was: index: int)
    parent_subsection: Optional[str] = None  # nearest preceding TitleElement text
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
    Segmented risk factors with preserved metadata.

    Internal Pydantic fields retain the original names (segments, total_segments)
    for code compatibility.  JSON output is written in the v2 structured schema
    (document_info / processing_metadata / section_metadata / chunks) by save_to_json.
    load_from_json handles both the old flat schema and the new structured schema.
    """
    model_config = ConfigDict(validate_assignment=True)

    segments: List[RiskSegment]
    sic_code: Optional[str] = None
    sic_name: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    form_type: Optional[str] = None
    fiscal_year: Optional[str] = None          # populated from metadata (Fix 6C)
    section_title: Optional[str] = None
    section_identifier: Optional[str] = None   # e.g. "part1item1a"
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
        Save segmented risks to JSON in the v2 structured schema (Fix 6C).

        Output structure:
            document_info / processing_metadata / section_metadata / chunks
        """
        output_path = Path(output_path)

        if output_path.suffix != '.json':
            output_path = output_path.with_suffix('.json')

        if output_path.exists() and not overwrite:
            raise FileExistsError(f"File exists: {output_path}. Set overwrite=True.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Fix 6C: derive fiscal_year — prefer model field, fallback to filename
        fiscal_year = self.fiscal_year
        if fiscal_year is None:
            fy_match = re.search(r'_(\d{4})[_.]', output_path.stem)
            fiscal_year = fy_match.group(1) if fy_match else None

        # Fix 6C: processing_metadata from config (lazy import to avoid top-level coupling)
        try:
            from src.config import settings as _cfg  # pylint: disable=import-outside-toplevel
            finbert_model = _cfg.models.default_model  # pylint: disable=no-member
        except Exception:  # pragma: no cover
            finbert_model = "ProsusAI/finbert"

        num_tables = (
            self.metadata.get('element_type_counts', {}).get('TableElement', 0)
        )

        data = {
            'version': '1.0',
            'document_info': {
                'company_name': self.company_name,
                'ticker': self.ticker,
                'cik': self.cik,
                'sic_code': self.sic_code,
                'sic_name': self.sic_name,
                'form_type': self.form_type,
                'fiscal_year': fiscal_year,
            },
            'processing_metadata': {
                'parser_version': '1.0',
                'finbert_model': finbert_model,
                'chunking_strategy': 'sentence_level',
                'max_tokens_per_chunk': 512,
            },
            'section_metadata': {
                'identifier': self.section_identifier,
                'title': self.section_title,
                'cleaning_settings': {
                    'removed_html_tags': True,
                    'normalized_whitespace': True,
                    'removed_page_numbers': True,
                    'discarded_tables': True,
                },
                'stats': {
                    'total_chunks': self.total_segments,
                    'num_tables': num_tables,
                },
            },
            'chunks': [
                {
                    'chunk_id': seg.chunk_id,
                    'parent_subsection': seg.parent_subsection,
                    'text': seg.text,
                    'word_count': seg.word_count,
                    'char_count': seg.char_count,
                }
                for seg in self.segments
            ],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    @staticmethod
    def load_from_json(file_path: Union[str, Path]) -> 'SegmentedRisks':
        """
        Load segmented risks from JSON.  Handles both the old flat schema
        and the new v2 structured schema (Fix 6C backward compat).
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # New structured schema: top-level key is 'document_info'
        if 'document_info' in data:
            di = data.get('document_info', {})
            sm = data.get('section_metadata', {})
            stats = sm.get('stats', {})
            raw_chunks = data.get('chunks', [])
            segments = [
                RiskSegment(
                    chunk_id=c.get('chunk_id', f"1A_{i+1:03d}"),
                    parent_subsection=c.get('parent_subsection'),
                    text=c.get('text', ''),
                    word_count=c.get('word_count', 0),
                    char_count=c.get('char_count', 0),
                )
                for i, c in enumerate(raw_chunks)
            ]
            return SegmentedRisks(
                segments=segments,
                sic_code=di.get('sic_code'),
                sic_name=di.get('sic_name'),
                cik=di.get('cik'),
                ticker=di.get('ticker'),
                company_name=di.get('company_name'),
                form_type=di.get('form_type'),
                fiscal_year=di.get('fiscal_year'),
                section_title=sm.get('title'),
                section_identifier=sm.get('identifier'),
                total_segments=stats.get('total_chunks', len(segments)),
                metadata=data.get('processing_metadata', {}),
            )

        # Old flat schema: top-level 'segments' list
        for drop_key in ('version', 'filing_name', 'num_segments'):
            data.pop(drop_key, None)

        # Map old index-based segments to new chunk_id format
        raw_segs = data.pop('segments', [])
        segments = []
        for i, s in enumerate(raw_segs):
            chunk_id = s.get('chunk_id') or f"1A_{i+1:03d}"
            segments.append(RiskSegment(
                chunk_id=chunk_id,
                parent_subsection=s.get('parent_subsection'),
                text=s.get('text', ''),
                word_count=s.get('word_count', 0),
                char_count=s.get('char_count', 0),
            ))
        data['segments'] = segments
        return SegmentedRisks.model_validate(data)
