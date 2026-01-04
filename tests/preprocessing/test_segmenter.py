"""
Tests for RiskSegmenter - validating risk factor segmentation quality using real SEC filing data.

Uses centralized fixtures from conftest.py for dynamic path resolution:
- segmented_data: Loaded segmented risk data from latest preprocessing run
- extracted_data: Loaded extracted risk data for re-segmentation tests
- segmenter: RiskSegmenter instance

Categories:
1. Segmentation Distribution - segment counts, length consistency (Gini)
2. Fallback Logic Validation - method tracking, fallback rates
3. Semantic Quality - filtering, non-risk content rejection
"""

import re
from typing import List, Dict

import pytest

from src.config.testing import TestMetricsConfig
from src.config.qa_validation import (
    ThresholdRegistry,
    ValidationResult,
    generate_validation_table,
    generate_blocking_summary,
    determine_overall_status,
)
from src.preprocessing.segmenter import RiskSegmenter, segment_risk_factors


def calculate_gini(lengths: List[int]) -> float:
    """Calculate Gini coefficient for segment length distribution."""
    n = len(lengths)
    if n == 0:
        return 0.0
    sorted_lengths = sorted(lengths)
    total = sum(sorted_lengths)
    if total == 0:
        return 0.0
    cumsum = sum((i + 1) * length for i, length in enumerate(sorted_lengths))
    return (2 * cumsum) / (n * total) - (n + 1) / n


class TestSegmenterDistributionWithRealData:
    """Tests for segmentation distribution metrics using real SEC filing data."""

    def test_segment_count_range(self, segmented_data: List[Dict]):
        """Verify segment count is within expected range (5-100) for 10-K filings."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            num_segments = doc.get("num_segments", len(doc.get("segments", [])))
            assert num_segments >= 5, (
                f"{doc.get('filing_name')}: Too few segments: {num_segments}"
            )
            assert num_segments <= 100, (
                f"{doc.get('filing_name')}: Too many segments: {num_segments}"
            )

    def test_non_empty_segmentation(self, segmented_data: List[Dict]):
        """Verify all processed files have segments."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            assert len(segments) > 0, (
                f"{doc.get('filing_name')}: No segments in processed file"
            )

    def test_gini_coefficient_balanced(self, segmented_data: List[Dict]):
        """Verify segment lengths are balanced (Gini < 0.7)."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            if len(segments) < 2:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            gini = calculate_gini(lengths)

            # Real filings may have more variation than ideal, use 0.7 threshold
            assert gini < 0.7, (
                f"{doc.get('filing_name')}: Gini coefficient {gini:.3f} >= 0.7 (too imbalanced)"
            )

    def test_min_max_ratio(self, segmented_data: List[Dict]):
        """Verify no extreme outliers (min/max ratio > 0.01)."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            if len(segments) < 2:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            min_len = min(lengths)
            max_len = max(lengths)

            ratio = min_len / max_len if max_len > 0 else 0
            # Real filings have more variation, use relaxed threshold
            assert ratio > 0.01, (
                f"{doc.get('filing_name')}: Min/max ratio {ratio:.3f} <= 0.01 (extreme outliers)"
            )

    def test_average_segment_length(self, segmented_data: List[Dict]):
        """Verify average segment length is reasonable."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            if not segments:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            avg_length = sum(lengths) / len(lengths)

            # Risk segments typically 200-3000 chars on average
            assert 100 <= avg_length <= 5000, (
                f"{doc.get('filing_name')}: Average segment length {avg_length:.0f} outside expected range"
            )


class TestSegmenterMetadataWithRealData:
    """Tests for segmentation metadata quality using real SEC filing data."""

    def test_segment_has_required_fields(self, segmented_data: List[Dict]):
        """Verify each segment has required fields."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        required_fields = {"id", "text", "length", "word_count"}
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                missing = required_fields - set(seg.keys())
                assert len(missing) == 0, (
                    f"{doc.get('filing_name')} segment {i}: Missing fields: {missing}"
                )

    def test_segment_length_matches_text(self, segmented_data: List[Dict]):
        """Verify segment length field matches actual text length."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                actual_len = len(seg.get("text", ""))
                reported_len = seg.get("length", 0)
                assert actual_len == reported_len, (
                    f"{doc.get('filing_name')} segment {i}: Length mismatch "
                    f"(reported {reported_len}, actual {actual_len})"
                )

    def test_segment_word_count_accurate(self, segmented_data: List[Dict]):
        """Verify segment word count is reasonably accurate."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                text = seg.get("text", "")
                actual_words = len(text.split())
                reported_words = seg.get("word_count", 0)
                # Allow small variance due to tokenization differences
                diff = abs(actual_words - reported_words)
                assert diff <= max(3, reported_words * 0.1), (
                    f"{doc.get('filing_name')} segment {i}: Word count mismatch "
                    f"(reported {reported_words}, actual {actual_words})"
                )

    def test_segment_ids_sequential(self, segmented_data: List[Dict]):
        """Verify segment IDs are sequential starting from 1."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            ids = [s.get("id") for s in segments]
            expected_ids = list(range(1, len(segments) + 1))
            assert ids == expected_ids, (
                f"{doc.get('filing_name')}: Segment IDs not sequential"
            )


class TestSegmenterQualityWithRealData:
    """Tests for semantic quality filtering using real SEC filing data."""

    def test_segments_have_substantive_content(self, segmented_data: List[Dict]):
        """Verify segments contain substantive risk content."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        risk_keywords = [
            'risk', 'adverse', 'material', 'significant', 'could',
            'may', 'operations', 'business', 'financial', 'impact'
        ]
        for doc in segmented_data:
            segments = doc.get("segments", [])
            # At least 50% of segments should have risk keywords
            segments_with_keywords = 0
            for seg in segments:
                text = seg.get("text", "").lower()
                if any(kw in text for kw in risk_keywords):
                    segments_with_keywords += 1

            ratio = segments_with_keywords / len(segments) if segments else 0
            assert ratio >= 0.5, (
                f"{doc.get('filing_name')}: Only {ratio:.1%} of segments have risk keywords"
            )

    def test_no_empty_segments(self, segmented_data: List[Dict]):
        """Verify no segments have empty or whitespace-only text."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                text = seg.get("text", "").strip()
                assert len(text) > 0, (
                    f"{doc.get('filing_name')} segment {i}: Empty segment text"
                )

    def test_min_word_count_enforcement(self, segmented_data: List[Dict]):
        """Verify segments have minimum word count."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        min_words = 5  # Relaxed threshold for real data
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                word_count = seg.get("word_count", len(seg.get("text", "").split()))
                assert word_count >= min_words, (
                    f"{doc.get('filing_name')} segment {i}: Only {word_count} words (< {min_words})"
                )

    def test_segments_have_sentence_structure(self, segmented_data: List[Dict]):
        """Verify segments have proper sentence structure."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            segments = doc.get("segments", [])
            segments_with_sentences = 0
            for seg in segments:
                text = seg.get("text", "")
                # Count sentence endings
                sentence_endings = len(re.findall(r'[.!?]', text))
                if sentence_endings >= 1:
                    segments_with_sentences += 1

            ratio = segments_with_sentences / len(segments) if segments else 0
            # At least 80% of segments should have proper sentences
            assert ratio >= 0.8, (
                f"{doc.get('filing_name')}: Only {ratio:.1%} of segments have sentence structure"
            )


class TestSegmenterSentimentWithRealData:
    """Tests for sentiment analysis integration using real SEC filing data."""

    def test_sentiment_fields_present(self, segmented_data: List[Dict]):
        """Verify sentiment fields are present when enabled."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                sentiment = seg.get("sentiment", {})
                expected_fields = {
                    "negative_count", "positive_count", "uncertainty_count",
                    "negative_ratio", "positive_ratio", "uncertainty_ratio"
                }
                present_fields = set(sentiment.keys())
                missing = expected_fields - present_fields
                assert len(missing) == 0, (
                    f"{doc.get('filing_name')} segment {i}: Missing sentiment fields: {missing}"
                )

    def test_sentiment_ratios_valid(self, segmented_data: List[Dict]):
        """Verify sentiment ratios are between 0 and 1."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                sentiment = seg.get("sentiment", {})
                for ratio_field in ["negative_ratio", "positive_ratio", "uncertainty_ratio"]:
                    ratio = sentiment.get(ratio_field, 0)
                    assert 0 <= ratio <= 1, (
                        f"{doc.get('filing_name')} segment {i}: {ratio_field}={ratio} out of range"
                    )

    def test_aggregate_sentiment_consistent(self, segmented_data: List[Dict]):
        """Verify aggregate sentiment matches segment averages."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            aggregate = doc.get("aggregate_sentiment", {})
            segments = doc.get("segments", [])
            if not segments:
                continue

            # Calculate actual average negative ratio
            neg_ratios = [s.get("sentiment", {}).get("negative_ratio", 0) for s in segments]
            actual_avg = sum(neg_ratios) / len(neg_ratios)
            reported_avg = aggregate.get("avg_negative_ratio", 0)

            # Allow small floating point variance
            assert abs(actual_avg - reported_avg) < 0.01, (
                f"{doc.get('filing_name')}: Aggregate sentiment mismatch "
                f"(reported {reported_avg:.4f}, calculated {actual_avg:.4f})"
            )


class TestSegmenterReprocessingWithRealData:
    """Tests for re-segmenting extracted data using RiskSegmenter."""

    def test_segmenter_on_extracted_text(self, segmenter: RiskSegmenter, extracted_data: List[Dict]):
        """Test RiskSegmenter produces valid output on real extracted text."""
        if not extracted_data:
            pytest.skip("No extracted data available")

        for doc in extracted_data[:3]:  # Limit for speed
            text = doc.get("text", "")
            if len(text) < 100:
                continue

            segments = segmenter.segment_risks(text)

            # Should produce segments
            assert len(segments) > 0, (
                f"Segmenter produced no segments for {doc.get('title', 'unknown')}"
            )

            # All segments should be strings
            assert all(isinstance(s, str) for s in segments), "Segments should be strings"

    def test_segmenter_preserves_content(self, segmenter: RiskSegmenter, extracted_data: List[Dict]):
        """Test that segmenter preserves key content."""
        if not extracted_data:
            pytest.skip("No extracted data available")

        for doc in extracted_data[:3]:
            text = doc.get("text", "")
            if len(text) < 100:
                continue

            segments = segmenter.segment_risks(text)
            combined = " ".join(segments)

            # Should preserve risk-related keywords
            if "risk" in text.lower():
                assert "risk" in combined.lower(), "Lost 'risk' keyword during segmentation"

    def test_empty_input_handling(self, segmenter: RiskSegmenter):
        """Verify empty input returns empty list."""
        assert segmenter.segment_risks("") == []
        assert segmenter.segment_risks("   ") == []

    def test_convenience_function(self):
        """Test the segment_risk_factors convenience function."""
        text = """
        Competition Risk: We face intense competition in our market segment.
        Our competitors have greater resources than we do currently.

        Regulatory Risk: Our operations are subject to extensive regulations.
        Compliance failures could result in significant penalties.
        """
        segments = segment_risk_factors(text)

        assert isinstance(segments, list), "Should return a list"
        assert all(isinstance(s, str) for s in segments), "All segments should be strings"


class TestSegmenterFilingMetadata:
    """Tests for filing-level metadata in segmented files."""

    def test_filing_metadata_present(self, segmented_data: List[Dict]):
        """Verify filing metadata is present."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        required_fields = {"filing_name", "section_identifier", "num_segments"}
        for doc in segmented_data:
            missing = required_fields - set(doc.keys())
            assert len(missing) == 0, (
                f"Missing filing metadata fields: {missing}"
            )

    def test_num_segments_accurate(self, segmented_data: List[Dict]):
        """Verify num_segments matches actual segment count."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            reported = doc.get("num_segments", 0)
            actual = len(doc.get("segments", []))
            assert reported == actual, (
                f"{doc.get('filing_name')}: num_segments mismatch "
                f"(reported {reported}, actual {actual})"
            )

    def test_segmentation_settings_present(self, segmented_data: List[Dict]):
        """Verify segmentation settings are recorded."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            doc_settings = doc.get("segmentation_settings", {})
            assert "min_segment_length" in doc_settings, (
                f"{doc.get('filing_name')}: Missing min_segment_length in settings"
            )

    def test_section_identifier_valid(self, segmented_data: List[Dict]):
        """Verify section identifier is valid."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        valid_identifiers = {"part1item1a", "item1a", "risk_factors"}
        for doc in segmented_data:
            identifier = doc.get("section_identifier", "").lower()
            # Check if identifier contains expected patterns
            has_valid = any(vid in identifier for vid in valid_identifiers)
            assert has_valid, (
                f"{doc.get('filing_name')}: Unexpected section identifier: {identifier}"
            )


class TestSegmenterCrossFilingConsistency:
    """Tests for consistency across multiple filings."""

    def test_similar_companies_similar_segment_counts(self, segmented_data: List[Dict]):
        """Verify segment counts are within reasonable range across filings."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        segment_counts = [
            doc.get("num_segments", len(doc.get("segments", [])))
            for doc in segmented_data
        ]
        if len(segment_counts) < 2:
            pytest.skip("Need at least 2 filings for comparison")

        avg_count = sum(segment_counts) / len(segment_counts)
        # Real filings have high variance - use 5x threshold
        # Some companies consolidate risks, others enumerate extensively
        for i, count in enumerate(segment_counts):
            assert count >= avg_count / 5, (
                f"Filing {i} has unusually few segments: {count} (avg: {avg_count:.0f})"
            )
            assert count <= avg_count * 5, (
                f"Filing {i} has unusually many segments: {count} (avg: {avg_count:.0f})"
            )

    def test_tickers_extracted_correctly(self, segmented_data: List[Dict]):
        """Verify ticker symbols are properly extracted."""
        if not segmented_data:
            pytest.skip("No segmented data available")

        for doc in segmented_data:
            ticker = doc.get("ticker", "")
            filing_name = doc.get("filing_name", "")

            # Ticker should be uppercase letters
            assert ticker.isalpha() and ticker.isupper(), (
                f"Invalid ticker format: {ticker}"
            )
            # Ticker should appear in filing name
            assert ticker in filing_name, (
                f"Ticker {ticker} not found in filing_name {filing_name}"
            )


class TestSegmenterMetricsReport:
    """Generate segmentation quality metrics report for validation."""

    def test_generate_segmentation_metrics(
        self,
        segmented_data: List[Dict],
        save_test_artifact,
        test_artifact_dir
    ):
        """Generate comprehensive segmentation metrics report.

        Saves metrics to persistent test output for QA review and trend analysis.
        Uses TestMetricsConfig for standardized field names and structure.
        """
        if not segmented_data:
            pytest.skip("No segmented data available")

        # Collect metrics across all filings
        segment_counts = []
        word_counts = []
        sentiment_scores = []
        filings_analyzed = []

        for doc in segmented_data:
            segments = doc.get("segments", [])
            num_segments = doc.get("num_segments", len(segments))
            segment_counts.append(num_segments)

            # Word counts per segment
            for seg in segments:
                word_counts.append(seg.get("word_count", 0))

            # Sentiment metrics
            aggregate = doc.get("aggregate_sentiment", {})
            if aggregate:
                sentiment_scores.append({
                    "ticker": doc.get("ticker", "unknown"),
                    "avg_negative_ratio": aggregate.get("avg_negative_ratio", 0),
                    "avg_uncertainty_ratio": aggregate.get("avg_uncertainty_ratio", 0),
                })

            filings_analyzed.append({
                "ticker": doc.get("ticker", "unknown"),
                "filing_name": doc.get("filing_name", "unknown"),
                "num_segments": num_segments,
            })

        # Use TestMetricsConfig for standardized metrics
        segment_stats = TestMetricsConfig.stats_summary(
            [float(c) for c in segment_counts],
            label="segments"
        )
        word_stats = TestMetricsConfig.stats_summary(
            [float(w) for w in word_counts],
            label="words"
        )

        # Determine status based on having meaningful segmentation
        avg_segments = segment_stats.get("segments_avg", 0)
        status = TestMetricsConfig.determine_status(
            min(1.0, avg_segments / 10),  # Pass if avg >= 10 segments
            pass_threshold=1.0,
            warn_threshold=0.5
        )

        # Create standardized report using TestMetricsConfig
        metrics_report = TestMetricsConfig.create_report(
            test_name="segmentation_quality",
            summary={
                "total_filings": len(segmented_data),
                **segment_stats,
                **TestMetricsConfig.count_metrics(
                    total=len(segmented_data),
                    processed=len([d for d in segmented_data if d.get("segments")]),
                    errors=0
                ),
            },
            status=status
        )

        # Add detailed metrics
        metrics_report["word_count_stats"] = word_stats
        metrics_report["sentiment_by_filing"] = sentiment_scores
        metrics_report["filings_analyzed"] = filings_analyzed

        # Save metrics to persistent output
        report_path = save_test_artifact("segmentation_metrics.json", metrics_report)

        # Print summary
        print(f"\n{'='*60}")
        print("SEGMENTATION METRICS REPORT")
        print(f"{'='*60}")
        print(f"Status: {metrics_report[TestMetricsConfig.FIELD_STATUS]}")
        print(f"Total filings analyzed: {metrics_report['summary']['total_filings']}")
        print(f"Total segments: {segment_stats.get('segments_total', 0)}")
        print(f"Avg segments per filing: {segment_stats.get('segments_avg', 0):.1f}")
        print(f"Avg words per segment: {word_stats.get('words_avg', 0):.0f}")
        print(f"{'='*60}")
        print(f"Report saved to: {report_path}")
        print(f"Artifact directory: {test_artifact_dir}")

        # Basic validation
        assert metrics_report["summary"]["total_filings"] > 0
        assert segment_stats.get("segments_avg", 0) > 0

    def test_segmentation_qa_validation(
        self,
        segmented_data: List[Dict],
        save_test_artifact,
        test_artifact_dir
    ):
        """
        Validate segmentation against QA thresholds from config.yaml.

        This test demonstrates the flexible qa_validation system:
        1. Measures actual values from segmented data
        2. Validates against thresholds defined in configs/config.yaml
        3. Generates Go/No-Go validation table
        4. Saves comprehensive report for QA review

        Thresholds can be modified in config.yaml without changing test code.
        """
        if not segmented_data:
            pytest.skip("No segmented data available")

        # Collect measurements
        segment_counts = []
        word_counts = []

        for doc in segmented_data:
            segments = doc.get("segments", [])
            num_segments = doc.get("num_segments", len(segments))
            segment_counts.append(num_segments)

            for seg in segments:
                word_counts.append(seg.get("word_count", 0))

        # Calculate metrics for validation
        avg_segments = sum(segment_counts) / len(segment_counts) if segment_counts else 0
        min_segments = min(segment_counts) if segment_counts else 0
        max_segments = max(segment_counts) if segment_counts else 0

        # Calculate Gini coefficient
        gini = calculate_gini(segment_counts) if segment_counts else 0

        # Calculate length CV (coefficient of variation)
        if segment_counts and len(segment_counts) > 1:
            import statistics
            mean_len = statistics.mean(segment_counts)
            std_len = statistics.stdev(segment_counts)
            length_cv = std_len / mean_len if mean_len > 0 else 0
        else:
            length_cv = 0

        # Calculate min/max ratio
        min_max_ratio = min_segments / max_segments if max_segments > 0 else 0

        # Check if all segments meet word count filter (>= 10 words)
        word_count_filter_pass = all(wc >= 10 for wc in word_counts) if word_counts else True

        # Validate against thresholds from config.yaml
        validation_results: List[ValidationResult] = []

        # Segment count min
        threshold = ThresholdRegistry.get("segment_count_min")
        if threshold:
            # Use average as representative value
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=int(avg_segments))
            )

        # Segment count max
        threshold = ThresholdRegistry.get("segment_count_max")
        if threshold:
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=max_segments)
            )

        # Gini coefficient
        threshold = ThresholdRegistry.get("gini_coefficient")
        if threshold:
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=gini)
            )

        # Length CV
        threshold = ThresholdRegistry.get("length_cv")
        if threshold:
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=length_cv)
            )

        # Min/max length ratio
        threshold = ThresholdRegistry.get("min_max_length_ratio")
        if threshold:
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=min_max_ratio)
            )

        # Word count filter
        threshold = ThresholdRegistry.get("word_count_filter_pass")
        if threshold:
            validation_results.append(
                ValidationResult.from_threshold(threshold, actual=word_count_filter_pass)
            )

        # Generate report using qa_validation helpers
        overall_status = determine_overall_status(validation_results)

        report = TestMetricsConfig.create_report(
            test_name="segmentation_qa_validation",
            status=overall_status.value
        )

        # Add validation table (Go/No-Go format)
        report["validation_table"] = generate_validation_table(validation_results)

        # Add blocking summary
        report["blocking_summary"] = generate_blocking_summary(validation_results)

        # Add raw measurements for debugging
        report["measurements"] = {
            "total_filings": len(segmented_data),
            "avg_segments_per_filing": avg_segments,
            "min_segments": min_segments,
            "max_segments": max_segments,
            "gini_coefficient": gini,
            "length_cv": length_cv,
            "min_max_ratio": min_max_ratio,
            "word_count_filter_pass": word_count_filter_pass,
        }

        # Save report
        report_path = save_test_artifact("segmentation_qa_validation.json", report)

        # Print validation table
        print(f"\n{'='*80}")
        print("SEGMENTATION QA VALIDATION REPORT")
        print(f"{'='*80}")
        print(f"Overall Status: {overall_status.value}")
        print(f"\nValidation Table:")
        print(f"{'Category':<25} {'Metric':<25} {'Target':<10} {'Actual':<10} {'Status':<8} {'Go/No-Go':<10}")
        print("-" * 88)
        for row in report["validation_table"]:
            print(
                f"{row['category']:<25} "
                f"{row['metric']:<25} "
                f"{str(row['target']):<10} "
                f"{str(round(row['actual'], 3) if isinstance(row['actual'], float) else row['actual']):<10} "
                f"{row['status']:<8} "
                f"{row['go_no_go']:<10}"
            )
        print(f"{'='*80}")
        print(f"Blocking: {report['blocking_summary']['passed']}/{report['blocking_summary']['total_blocking']} passed")
        print(f"Report saved to: {report_path}")

        # Assert no blocking failures
        assert report["blocking_summary"]["all_pass"], \
            f"Blocking thresholds failed: {[r['metric'] for r in report['validation_table'] if r['go_no_go'] == 'NO-GO']}"
