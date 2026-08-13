"""
Pydantic models for risk factor segmentation.

Contains data structures for individual risk segments and segmented risk collections.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, ConfigDict


class RiskSegment(BaseModel):
    """Individual risk segment with structured chunk identifier (Fix 6B)"""
    model_config = ConfigDict(validate_assignment=True)

    chunk_id: str                           # "1A_001", "1A_002", … (was: index: int)
    parent_subsection: Optional[str] = None  # nearest preceding TitleElement text
    ancestors: List[str] = []               # D2-A: outermost→innermost title breadcrumb
    text: str
    word_count: int = 0
    char_count: int = 0
    segment_hash: Optional[str] = None      # sha256(ticker+fy+section+chunk_id+text[:200])[:12]
    sentiment: Optional[Dict[str, Any]] = None  # Loughran-McDonald features (optional)

    @staticmethod
    def compute_hash(ticker: str, fiscal_year: str, section_id: str, chunk_id: str, text: str) -> str:
        """Compute a globally unique 12-char segment identifier."""
        import hashlib
        raw = f"{ticker}:{fiscal_year}:{section_id}:{chunk_id}:{text[:200]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

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
    # New fields from ADR-010 SGMLManifest (Stage 0)
    accession_number: Optional[str] = None   # e.g. "0000320193-21-000105"
    filed_as_of_date: Optional[str] = None   # YYYYMMDD
    # DEI ix:hidden fields (ADR-011)
    amendment_flag: Optional[bool] = None
    entity_filer_category: Optional[str] = None
    ein: Optional[str] = None
    # Section-level char counts for G-02 loss measurement
    raw_section_char_count: Optional[int] = None      # len(extracted.text) pre-TextCleaner
    cleaned_section_char_count: Optional[int] = None  # len(cleaned_text) post-TextCleaner
    # Boilerplate detection: True when section contains "no material change" language
    no_material_change: bool = False
    # v2.1: filing-level fields for single-serializer output
    filing_name: Optional[str] = None              # source filename
    sentiment_analysis_enabled: bool = False        # whether sentiment was computed
    aggregate_sentiment: Optional[Dict[str, float]] = None  # corpus-level averages

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

        # fiscal_year is sourced from SGMLHeader.period_of_report (100% EDGAR coverage).
        # Filename-based fallback removed (ADR-010): filing identity comes from the
        # form itself, not the downloaded file's name.
        fiscal_year = self.fiscal_year

        # Fix 6C: processing_metadata from config (lazy import to avoid top-level coupling)
        try:
            from src.config import settings as _cfg  # pylint: disable=import-outside-toplevel
            finbert_model = _cfg.models.default_model  # pylint: disable=no-member
            cleaning_settings = {
                'removed_html_tags':    _cfg.preprocessing.remove_html_tags,
                'normalized_whitespace': _cfg.preprocessing.normalize_whitespace,
                'removed_page_numbers': _cfg.preprocessing.remove_page_numbers,
                'discarded_tables':     True,
            }
        except Exception:  # pragma: no cover
            finbert_model = "ProsusAI/finbert"
            cleaning_settings = {
                'removed_html_tags': True,
                'normalized_whitespace': True,
                'removed_page_numbers': True,
                'discarded_tables': True,
            }

        num_tables = (
            self.metadata.get('element_type_counts', {}).get('TableElement', 0)
        )

        data: Dict[str, Any] = {
            'version': '2.1',
            'filing_name': self.filing_name,
            'document_info': {
                'company_name': self.company_name,
                'ticker': self.ticker,
                'cik': self.cik,
                'sic_code': self.sic_code,
                'sic_name': self.sic_name,
                'form_type': self.form_type,
                'fiscal_year': fiscal_year,
                'accession_number': self.accession_number,
                'filed_as_of_date': self.filed_as_of_date,
                'amendment_flag':        self.amendment_flag,
                'entity_filer_category': self.entity_filer_category,
                'ein':                   self.ein,
                'dei':                   self.metadata.get('dei') or {},
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
                'no_material_change': self.no_material_change,
                'cleaning_settings': cleaning_settings,
                'stats': {
                    'total_chunks': self.total_segments,
                    'num_tables': num_tables,
                    'raw_section_char_count':     self.raw_section_char_count,
                    'cleaned_section_char_count': self.cleaned_section_char_count,
                    'table_char_count': self.metadata.get('table_char_count'),
                    'pre_exclusion_char_count': self.metadata.get('pre_exclusion_char_count'),
                    'extraction_manifest': self.metadata.get('extraction_manifest'),
                    'segmentation_stats': self.metadata.get('segmentation_stats'),
                    'text_coverage': self.metadata.get('text_coverage'),
                },
            },
            'num_segments': self.total_segments,
            'sentiment_analysis_enabled': self.sentiment_analysis_enabled,
            'segments': [
                {
                    'chunk_id':          seg.chunk_id,
                    'parent_subsection': seg.parent_subsection,
                    'ancestors':         seg.ancestors,
                    'text':              seg.text,
                    'word_count':        seg.word_count,
                    'char_count':        seg.char_count,
                    **({'segment_hash': seg.segment_hash} if seg.segment_hash else {}),
                    **({'sentiment': seg.sentiment} if seg.sentiment else {}),
                }
                for seg in self.segments
            ],
        }

        if self.aggregate_sentiment is not None:
            data['aggregate_sentiment'] = self.aggregate_sentiment

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
            # Accept both 'segments' (v2.1) and 'chunks' (v1.0) keys
            raw_chunks = data.get('segments') or data.get('chunks', [])

            # Build segment list with full field support
            ticker = di.get('ticker')
            fiscal_year = di.get('fiscal_year')
            section_id = sm.get('identifier')

            segments = []
            for i, c in enumerate(raw_chunks):
                # Accept both 'chunk_id' and 'id' as the segment ID key
                raw_id = c.get('chunk_id') or c.get('id')
                chunk_id = str(raw_id) if raw_id is not None else f"1A_{i+1:03d}"
                seg = RiskSegment(
                    chunk_id=chunk_id,
                    parent_subsection=c.get('parent_subsection'),
                    ancestors=c.get('ancestors', []),
                    text=c.get('text', ''),
                    word_count=c.get('word_count', 0),
                    char_count=c.get('char_count', 0),
                    segment_hash=c.get('segment_hash'),
                    sentiment=c.get('sentiment'),
                )
                # Recompute hash for old files that lack it
                if seg.segment_hash is None and ticker and fiscal_year:
                    seg.segment_hash = RiskSegment.compute_hash(
                        ticker=ticker,
                        fiscal_year=fiscal_year,
                        section_id=section_id or '',
                        chunk_id=seg.chunk_id,
                        text=seg.text,
                    )
                segments.append(seg)

            # Restore metadata dict with stats that may be needed downstream
            restored_metadata: Dict[str, Any] = {
                'dei': di.get('dei', {}),
            }
            # Preserve text_coverage in metadata for downstream consumers
            if stats.get('text_coverage'):
                restored_metadata['text_coverage'] = stats['text_coverage']

            return SegmentedRisks(
                segments=segments,
                sic_code=di.get('sic_code'),
                sic_name=di.get('sic_name'),
                cik=di.get('cik'),
                ticker=ticker,
                company_name=di.get('company_name'),
                form_type=di.get('form_type'),
                fiscal_year=fiscal_year,
                accession_number=di.get('accession_number'),   # B-5 fix
                filed_as_of_date=di.get('filed_as_of_date'),   # B-5 fix
                amendment_flag=di.get('amendment_flag'),
                entity_filer_category=di.get('entity_filer_category'),
                ein=di.get('ein'),
                section_title=sm.get('title'),
                section_identifier=sm.get('identifier'),
                total_segments=stats.get('total_chunks', len(segments)),
                raw_section_char_count=stats.get('raw_section_char_count'),
                cleaned_section_char_count=stats.get('cleaned_section_char_count'),
                no_material_change=sm.get('no_material_change', False),
                filing_name=data.get('filing_name'),
                sentiment_analysis_enabled=data.get('sentiment_analysis_enabled', False),
                aggregate_sentiment=data.get('aggregate_sentiment'),
                metadata=restored_metadata,
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
                char_count=s.get('char_count') or s.get('length', 0),
            ))
        data['segments'] = segments
        return SegmentedRisks.model_validate(data)
