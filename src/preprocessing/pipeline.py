"""
Preprocessing Pipeline for SEC Filings

Orchestrates the complete preprocessing flow:
1. Parse - Parse HTML filing into semantic structure
2. Clean - Clean and normalize text
3. Extract - Extract specific sections with metadata
4. Segment - Split into individual risk segments

All metadata (sic_code, sic_name, cik, ticker, company_name) is preserved
throughout the pipeline.
"""

import logging
from pathlib import Path
from typing import Optional, Union, List

from pydantic import BaseModel, ConfigDict, Field

from .parser import SECFilingParser, ParsedFiling
from .cleaning import TextCleaner
from .extractor import SECSectionExtractor, ExtractedSection
from .segmenter import RiskSegmenter, SegmentedRisks
from .constants import SectionIdentifier

logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    """
    Configuration for the preprocessing pipeline (Pydantic V2)

    Attributes:
        remove_html: Whether to remove HTML tags from text
        deep_clean: Whether to apply NLP-based deep cleaning
        use_lemmatization: Whether to lemmatize words
        remove_stopwords: Whether to remove stop words
        remove_punctuation: Whether to remove punctuation
        remove_numbers: Whether to remove numbers
        min_segment_length: Minimum segment length (None = use default from settings)
        max_segment_length: Maximum segment length (None = use default from settings)
        semantic_model_name: SentenceTransformer model for semantic segmentation
        similarity_threshold: Cosine similarity threshold for semantic breaks
    """
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',  # Raise error on unknown fields
    )

    # Cleaning options
    remove_html: bool = Field(default=True, description="Remove HTML tags from text")
    deep_clean: bool = Field(default=False, description="Apply NLP-based deep cleaning")
    use_lemmatization: bool = Field(default=False, description="Lemmatize words")
    remove_stopwords: bool = Field(default=False, description="Remove stop words")
    remove_punctuation: bool = Field(default=False, description="Remove punctuation")
    remove_numbers: bool = Field(default=False, description="Remove numbers")

    # Segmentation options
    min_segment_length: Optional[int] = Field(
        default=None,
        description="Minimum segment length (None = use default from settings)"
    )
    max_segment_length: Optional[int] = Field(
        default=None,
        description="Maximum segment length (None = use default from settings)"
    )
    semantic_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="SentenceTransformer model for semantic segmentation"
    )
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for semantic breaks"
    )


class SECPreprocessingPipeline:
    """
    Complete preprocessing pipeline for SEC filings

    Flow: Parse → Clean → Extract → Segment

    All metadata is preserved through the pipeline:
    - sic_code: Standard Industrial Classification code
    - sic_name: SIC industry name (e.g., "PHARMACEUTICAL PREPARATIONS")
    - cik: Central Index Key
    - ticker: Stock ticker symbol
    - company_name: Company name

    Example:
        >>> pipeline = SECPreprocessingPipeline()
        >>> result = pipeline.process_filing(
        ...     "data/raw/AAPL_10K.html",
        ...     form_type="10-K"
        ... )
        >>> print(f"Company: {result.company_name}")
        >>> print(f"SIC: {result.sic_code} - {result.sic_name}")
        >>> print(f"Segments: {len(result.segments)}")
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the preprocessing pipeline

        Args:
            config: Pipeline configuration. Uses defaults if not provided.
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.parser = SECFilingParser()
        self.cleaner = TextCleaner(
            use_lemmatization=self.config.use_lemmatization,
            remove_stopwords=self.config.remove_stopwords,
            remove_punctuation=self.config.remove_punctuation,
            remove_numbers=self.config.remove_numbers,
        )
        self.extractor = SECSectionExtractor()
        self.segmenter = RiskSegmenter(
            min_length=self.config.min_segment_length,
            max_length=self.config.max_segment_length,
            semantic_model_name=self.config.semantic_model_name,
            similarity_threshold=self.config.similarity_threshold,
        )

    def process_filing(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        section: SectionIdentifier = SectionIdentifier.ITEM_1A_RISK_FACTORS,
        save_output: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
    ) -> Optional[SegmentedRisks]:
        """
        Process a SEC filing through the complete pipeline

        Flow:
        1. Parse HTML → ParsedFiling (with metadata)
        2. Extract section → ExtractedSection (with metadata)
        3. Clean text → cleaned text
        4. Segment → SegmentedRisks (with metadata)

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            section: Section to extract (default: Risk Factors)
            save_output: Optional path to save the result as JSON
            overwrite: Whether to overwrite existing output file

        Returns:
            SegmentedRisks with segments and preserved metadata, or None if extraction fails

        Example:
            >>> pipeline = SECPreprocessingPipeline()
            >>> result = pipeline.process_filing("AAPL_10K.html")
            >>> print(f"Found {len(result)} risk segments")
            >>> print(f"SIC: {result.sic_name}")
        """
        file_path = Path(file_path)
        logger.info("Processing filing: %s", file_path.name)

        # Step 1: Parse
        logger.info("Step 1/4: Parsing HTML filing...")
        parsed = self.parser.parse_filing(file_path, form_type)
        logger.info(
            "Parsed %d elements. Metadata: CIK=%s, SIC=%s (%s)",
            len(parsed),
            parsed.metadata.get('cik'),
            parsed.metadata.get('sic_code'),
            parsed.metadata.get('sic_name'),
        )

        # Step 2: Extract section (metadata flows through)
        logger.info("Step 2/4: Extracting section '%s'...", section.value)
        extracted = self.extractor.extract_section(parsed, section)

        if extracted is None:
            logger.warning("Section '%s' not found in filing", section.value)
            return None

        logger.info(
            "Extracted section: %d chars, %d subsections",
            len(extracted.text),
            len(extracted.subsections),
        )

        # Step 3: Clean text
        logger.info("Step 3/4: Cleaning text...")
        if self.config.remove_html:
            cleaned_text = self.cleaner.remove_html_tags(extracted.text)
        else:
            cleaned_text = extracted.text

        cleaned_text = self.cleaner.clean_text(
            cleaned_text,
            deep_clean=self.config.deep_clean
        )
        logger.info("Cleaned text: %d chars", len(cleaned_text))

        # Step 4: Segment (metadata preserved)
        logger.info("Step 4/4: Segmenting risks...")
        result = self.segmenter.segment_extracted_section(
            extracted,
            cleaned_text=cleaned_text
        )
        logger.info("Created %d segments", len(result))

        # Save if requested
        if save_output:
            output_path = result.save_to_json(save_output, overwrite=overwrite)
            logger.info("Saved result to: %s", output_path)

        return result

    def process_risk_factors(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        save_output: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
    ) -> Optional[SegmentedRisks]:
        """
        Convenience method to process Risk Factors section

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            save_output: Optional path to save the result as JSON
            overwrite: Whether to overwrite existing output file

        Returns:
            SegmentedRisks with risk segments and metadata
        """
        if form_type.upper() in ["10-K", "10K"]:
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS
        else:
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q

        return self.process_filing(
            file_path,
            form_type=form_type,
            section=section,
            save_output=save_output,
            overwrite=overwrite,
        )

    def process_batch(
        self,
        file_paths: List[Union[str, Path]],
        form_type: str = "10-K",
        output_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
    ) -> List[SegmentedRisks]:
        """
        Process multiple filings

        Args:
            file_paths: List of paths to HTML filing files
            form_type: Type of SEC form ("10-K" or "10-Q")
            output_dir: Optional directory to save results
            overwrite: Whether to overwrite existing files

        Returns:
            List of SegmentedRisks objects
        """
        results = []

        for file_path in file_paths:
            file_path = Path(file_path)

            # Generate output path if output_dir is provided
            save_output = None
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                save_output = output_dir / f"{file_path.stem}_segmented.json"

            try:
                result = self.process_risk_factors(
                    file_path,
                    form_type=form_type,
                    save_output=save_output,
                    overwrite=overwrite,
                )
                if result:
                    results.append(result)
            except Exception as e:
                logger.error("Failed to process %s: %s", file_path.name, e)

        logger.info("Processed %d/%d filings successfully", len(results), len(file_paths))
        return results


def process_filing(
    file_path: Union[str, Path],
    form_type: str = "10-K",
    deep_clean: bool = False,
    save_output: Optional[Union[str, Path]] = None,
) -> Optional[SegmentedRisks]:
    """
    Convenience function to process a single SEC filing

    Args:
        file_path: Path to the HTML filing file
        form_type: Type of SEC form ("10-K" or "10-Q")
        deep_clean: Whether to apply NLP-based deep cleaning
        save_output: Optional path to save the result

    Returns:
        SegmentedRisks with segments and metadata

    Example:
        >>> from src.preprocessing.pipeline import process_filing
        >>> result = process_filing("data/raw/AAPL_10K.html")
        >>> print(f"Company: {result.company_name}")
        >>> print(f"SIC: {result.sic_code} - {result.sic_name}")
        >>> for seg in result.segments[:3]:
        ...     print(f"- {seg.text[:100]}...")
    """
    config = PipelineConfig(deep_clean=deep_clean)
    pipeline = SECPreprocessingPipeline(config)
    return pipeline.process_risk_factors(
        file_path,
        form_type=form_type,
        save_output=save_output,
    )


if __name__ == "__main__":
    import sys

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("SEC Preprocessing Pipeline")
    print("=" * 50)
    print("\nFlow: Parse → Clean → Extract → Segment")
    print("\nMetadata preserved throughout:")
    print("  - sic_code, sic_name")
    print("  - cik, ticker, company_name")
    print("  - form_type")

    # Example usage
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        form_type = sys.argv[2] if len(sys.argv) > 2 else "10-K"

        result = process_filing(file_path, form_type=form_type)

        if result:
            print(f"\n{'=' * 50}")
            print(f"Company: {result.company_name}")
            print(f"CIK: {result.cik}")
            print(f"SIC Code: {result.sic_code}")
            print(f"SIC Name: {result.sic_name}")
            print(f"Form Type: {result.form_type}")
            print(f"Total Segments: {len(result)}")
            print(f"\nFirst 3 segments:")
            for seg in result.segments[:3]:
                preview = seg.text[:150].replace('\n', ' ')
                print(f"  [{seg.index}] {preview}...")
        else:
            print("Failed to process filing")
    else:
        print("\nUsage: python -m src.preprocessing.pipeline <file_path> [form_type]")
        print("Example: python -m src.preprocessing.pipeline data/raw/AAPL_10K.html 10-K")
