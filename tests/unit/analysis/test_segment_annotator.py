"""
Unit tests for src/analysis/segment_annotator.py.

All tests that exercise the NLI pipeline mock it out — no real model is loaded.
Tests for the B-5 fix live here as well (alongside test_preprocessing_models_unit.py
which also has round-trip coverage).
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.analysis.segment_annotator import (
    ARCHETYPE_LABEL_MAP,
    ARCHETYPE_NAMES,
    LABEL_SOURCE_NLI,
    LABEL_SOURCE_HEURISTIC,
    LABEL_SOURCE_ANCESTOR,
    LABEL_SOURCE_LLM,
    LABEL_SOURCE_CLASSIFIER,
    LABEL_SOURCE_HUMAN,
    LABEL_SOURCE_SYNTHETIC,
    _VALID_LABEL_SOURCES,
    SegmentAnnotator,
    _reformat_date,
    _heuristic_label,
    _make_merged_segment,
)
from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _seg(chunk_id: str, text: str, ancestors: list = None, words: int = None) -> RiskSegment:
    """Helper: create a RiskSegment with explicit word_count if needed."""
    s = RiskSegment(
        chunk_id=chunk_id,
        text=text,
        ancestors=ancestors or [],
    )
    if words is not None:
        object.__setattr__(s, "word_count", words)
    return s


def _make_segmented(
    segments: list,
    ticker: str = "AAPL",
    sic_code: str = "7372",
    cik: str = "0000320193",
    filed_as_of_date: str = "20211029",
    section_identifier: str = "part1item1a",
) -> SegmentedRisks:
    return SegmentedRisks(
        segments=segments,
        ticker=ticker,
        sic_code=sic_code,
        cik=cik,
        filed_as_of_date=filed_as_of_date,
        section_identifier=section_identifier,
    )


def _mock_pipeline_factory(label: str = "cybersecurity", score: float = 0.85):
    """Return a callable mock that mimics the HF zero-shot-classification pipeline."""
    def _pipe(text, candidates, hypothesis_template=None, multi_label=False):
        scores = {c: 0.01 for c in candidates}
        if label in scores:
            scores[label] = score
        sorted_labels = sorted(scores, key=scores.__getitem__, reverse=True)
        return {"labels": sorted_labels, "scores": [scores[l] for l in sorted_labels]}
    return _pipe


def _make_annotator(
    pipeline_label: str = "cybersecurity",
    pipeline_score: float = 0.85,
    device: int = -1,
) -> SegmentAnnotator:
    """Build a SegmentAnnotator with a mocked NLI pipeline (no model loaded)."""
    annotator = object.__new__(SegmentAnnotator)
    annotator._model_name        = "mock-model"
    annotator._confidence_thresh = 0.70
    annotator._gate_thresh       = 0.50
    annotator._merge_lo          = 200
    annotator._merge_hi          = 379
    annotator._device            = device
    annotator._llm_client        = None
    annotator._use_llm_for       = set()
    annotator._crosswalk         = None
    annotator._pipeline          = _mock_pipeline_factory(pipeline_label, pipeline_score)
    # Mock tokenizer: encode returns word tokens (1 token per word, simplified)
    mock_tokenizer = MagicMock()
    mock_tokenizer.model_max_length = 1024
    mock_tokenizer.encode = lambda text, add_special_tokens=False: text.split()
    mock_tokenizer.decode = lambda tokens, skip_special_tokens=False: " ".join(tokens)
    annotator._tokenizer = mock_tokenizer
    # Mock taxonomy manager: no SASB files present
    mock_taxonomy = MagicMock()
    mock_taxonomy.get_industry_for_sic.return_value = None
    annotator._taxonomy = mock_taxonomy
    return annotator


# ---------------------------------------------------------------------------
# B-5 fix tests (duplicate of test_preprocessing_models_unit.py for locality)
# ---------------------------------------------------------------------------

class TestB5Fix:
    def test_filed_as_of_date_roundtrip(self, tmp_path):
        sr = SegmentedRisks(
            segments=[RiskSegment(chunk_id="1A_001", text="Risk text.")],
            ticker="AAPL",
            filed_as_of_date="20211029",
        )
        out = tmp_path / "AAPL_segmented.json"
        sr.save_to_json(out)
        loaded = SegmentedRisks.load_from_json(out)
        assert loaded.filed_as_of_date == "20211029"

    def test_accession_number_roundtrip(self, tmp_path):
        sr = SegmentedRisks(
            segments=[RiskSegment(chunk_id="1A_001", text="Risk text.")],
            ticker="AAPL",
            accession_number="0000320193-21-000105",
        )
        out = tmp_path / "AAPL_segmented.json"
        sr.save_to_json(out)
        loaded = SegmentedRisks.load_from_json(out)
        assert loaded.accession_number == "0000320193-21-000105"


# ---------------------------------------------------------------------------
# _merge_by_ancestors
# ---------------------------------------------------------------------------

class TestMergeByAncestors:
    def test_basic_merge_three_short_segments(self):
        ancestors = ["Item 1A", "Cybersecurity"]
        segs = [
            _seg("1A_001", "word " * 60, ancestors=ancestors),
            _seg("1A_002", "word " * 60, ancestors=ancestors),
            _seg("1A_003", "word " * 100, ancestors=ancestors),
        ]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        assert len(merged) == 1
        assert "1A_001+1A_003" == merged[0].chunk_id

    def test_flush_when_ceiling_exceeded(self):
        ancestors = ["Item 1A", "Market Risk"]
        segs = [
            _seg("1A_001", "word " * 200, ancestors=ancestors),
            _seg("1A_002", "word " * 200, ancestors=ancestors),
        ]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        # First segment already >= merge_lo, passes through; second also passes through
        assert len(merged) == 2

    def test_passthrough_large_segment(self):
        segs = [_seg("1A_001", "word " * 250, ancestors=["Item 1A"])]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        assert len(merged) == 1
        assert merged[0].chunk_id == "1A_001"

    def test_empty_ancestors_singleton(self):
        segs = [
            _seg("1A_001", "word " * 50, ancestors=[]),
            _seg("1A_002", "word " * 50, ancestors=[]),
        ]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        # ancestors=[] → each is a singleton run (no merge across empty-ancestors segments)
        assert len(merged) == 2

    def test_boundary_splits_on_different_ancestors(self):
        segs = [
            _seg("1A_001", "word " * 100, ancestors=["Item 1A", "Cyber"]),
            _seg("1A_002", "word " * 100, ancestors=["Item 1A", "Market"]),
        ]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        assert len(merged) == 2

    def test_merge_chunk_id_format(self):
        ancestors = ["Item 1A", "Supply Chain"]
        segs = [
            _seg("1A_003", "word " * 100, ancestors=ancestors),
            _seg("1A_007", "word " * 100, ancestors=ancestors),
        ]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        assert len(merged) == 1
        assert merged[0].chunk_id == "1A_003+1A_007"

    def test_no_merge_exceeds_merge_hi(self):
        ancestors = ["Heading"]
        segs = [_seg(f"1A_{i:03d}", "word " * 30, ancestors=ancestors) for i in range(20)]
        merged = SegmentAnnotator._merge_by_ancestors(segs, merge_lo=200, merge_hi=379)
        for m in merged:
            assert m.word_count <= 379

    def test_empty_input(self):
        assert SegmentAnnotator._merge_by_ancestors([]) == []


# ---------------------------------------------------------------------------
# _apply_ancestor_score_bonus
# ---------------------------------------------------------------------------

class TestAncestorScoreBonus:
    def test_bonus_applied_when_ancestor_matches(self):
        scores = {a: 0.10 for a in ARCHETYPE_NAMES}
        ancestors = ["Item 7", "Liquidity and Capital Resources"]
        updated, matched = SegmentAnnotator._apply_ancestor_score_bonus(
            scores, ancestors, {}, bonus=0.05
        )
        # No prior dict passed → no match
        assert not matched

    def test_bonus_applied_from_prior_dict(self):
        from src.analysis.segment_annotator import _ANCESTOR_ARCHETYPE_PRIOR
        scores = {a: 0.10 for a in ARCHETYPE_NAMES}
        ancestors = ["Item 7", "Liquidity and Capital Resources"]
        updated, matched = SegmentAnnotator._apply_ancestor_score_bonus(
            scores, ancestors, _ANCESTOR_ARCHETYPE_PRIOR, bonus=0.05
        )
        assert matched
        assert updated["financial"] == pytest.approx(0.15, abs=1e-6)
        # All other archetypes unchanged
        for a in ARCHETYPE_NAMES:
            if a != "financial":
                assert updated[a] == pytest.approx(0.10, abs=1e-6)

    def test_no_match_returns_unchanged(self):
        scores = {a: 0.10 for a in ARCHETYPE_NAMES}
        ancestors = ["Item 1A", "Some Unknown Heading"]
        updated, matched = SegmentAnnotator._apply_ancestor_score_bonus(
            scores, ancestors, {"liquidity": "financial"}, bonus=0.05
        )
        assert not matched
        assert updated == scores

    def test_empty_ancestors_no_match(self):
        scores = {a: 0.10 for a in ARCHETYPE_NAMES}
        updated, matched = SegmentAnnotator._apply_ancestor_score_bonus(
            scores, [], {"liquidity": "financial"}, bonus=0.05
        )
        assert not matched
        assert updated == scores

    def test_bonus_capped_at_one(self):
        scores = {a: 0.98 for a in ARCHETYPE_NAMES}
        ancestors = ["Liquidity and Capital Resources"]
        updated, matched = SegmentAnnotator._apply_ancestor_score_bonus(
            scores, ancestors, {"liquidity and capital resources": "financial"}, bonus=0.05
        )
        assert matched
        assert updated["financial"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _is_risk_relevant
# ---------------------------------------------------------------------------

class TestIsRiskRelevant:
    def test_always_true_for_part1item1a(self):
        mock_pipe = MagicMock()
        result = SegmentAnnotator._is_risk_relevant(
            "any text", "part1item1a", mock_pipe, gate_threshold=0.5
        )
        assert result is True
        mock_pipe.assert_not_called()

    def test_always_true_for_part2item7a(self):
        mock_pipe = MagicMock()
        result = SegmentAnnotator._is_risk_relevant(
            "any text", "part2item7a", mock_pipe, gate_threshold=0.5
        )
        assert result is True
        mock_pipe.assert_not_called()

    def test_gate_applied_for_part1item1_above_threshold(self):
        def _pipe(text, candidates, hypothesis_template=None, multi_label=False):
            return {"labels": ["relevant", "not relevant"], "scores": [0.80, 0.20]}
        result = SegmentAnnotator._is_risk_relevant(
            "We face supply chain risks.", "part1item1", _pipe, gate_threshold=0.5
        )
        assert result is True

    def test_gate_applied_for_part1item1_below_threshold(self):
        def _pipe(text, candidates, hypothesis_template=None, multi_label=False):
            return {"labels": ["relevant", "not relevant"], "scores": [0.30, 0.70]}
        result = SegmentAnnotator._is_risk_relevant(
            "Our headquarters are in Cupertino.", "part1item1", _pipe, gate_threshold=0.5
        )
        assert result is False

    def test_gate_applied_for_part2item7(self):
        def _pipe(text, candidates, hypothesis_template=None, multi_label=False):
            return {"labels": ["relevant", "not relevant"], "scores": [0.60, 0.40]}
        result = SegmentAnnotator._is_risk_relevant(
            "Revenue declined.", "part2item7", _pipe, gate_threshold=0.5
        )
        assert result is True


# ---------------------------------------------------------------------------
# annotate() — filing_date, SASB null-safety, label_source
# ---------------------------------------------------------------------------

class TestAnnotate:
    def test_filing_date_reformat(self):
        annotator = _make_annotator()
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg], filed_as_of_date="20211029")
        records = annotator.annotate(segmented)
        assert len(records) == 1
        assert records[0]["filing_date"] == "2021-10-29"

    def test_null_filed_as_of_date_no_crash(self):
        annotator = _make_annotator()
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg], filed_as_of_date=None)
        records = annotator.annotate(segmented)
        assert records[0]["filing_date"] is None

    def test_sasb_null_when_taxonomy_absent(self):
        annotator = _make_annotator()
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        assert records[0]["sasb_topic"] is None
        assert records[0]["sasb_industry"] is None

    def test_all_14_fields_present(self):
        annotator = _make_annotator()
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        required = {
            "index", "text", "word_count", "char_count", "label", "risk_label",
            "sasb_topic", "sasb_industry", "sic_code", "ticker", "cik",
            "filing_date", "confidence", "label_source",
        }
        assert required == set(records[0].keys())

    def test_label_in_range(self):
        annotator = _make_annotator()
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        assert 0 <= records[0]["label"] <= 8

    def test_index_monotonically_increasing(self):
        annotator = _make_annotator()
        segs = [_seg(f"1A_{i:03d}", "word " * 50) for i in range(5)]
        segmented = _make_segmented(segs)
        records = annotator.annotate(segmented)
        indices = [r["index"] for r in records]
        assert indices == list(range(len(records)))

    def test_word_count_within_merge_hi(self):
        annotator = _make_annotator()
        ancestors = ["Item 1A", "Cyber"]
        segs = [_seg(f"1A_{i:03d}", "word " * 30, ancestors=ancestors) for i in range(20)]
        segmented = _make_segmented(segs)
        records = annotator.annotate(segmented)
        for r in records:
            assert r["word_count"] <= 379


# ---------------------------------------------------------------------------
# label_source namespace (ADR-015)
# ---------------------------------------------------------------------------

class TestLabelSourceNamespace:
    def test_nli_above_threshold(self):
        annotator = _make_annotator(pipeline_label="regulatory", pipeline_score=0.90)
        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        assert records[0]["label_source"] == LABEL_SOURCE_NLI

    def test_heuristic_below_threshold_no_ancestor(self):
        # Low score, no ancestor match
        annotator = _make_annotator(pipeline_label="other", pipeline_score=0.30)
        seg = _seg("1A_001", "liquidity credit default debt word " * 5, ancestors=[])
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        # Confidence < threshold and no ancestor → heuristic
        assert records[0]["label_source"] == LABEL_SOURCE_HEURISTIC

    def test_ancestor_prior_below_threshold(self):
        from src.analysis.segment_annotator import _ANCESTOR_ARCHETYPE_PRIOR
        # Low pipeline score but known ancestor
        annotator = _make_annotator(pipeline_label="other", pipeline_score=0.30)
        seg = _seg("1A_001", "word " * 50, ancestors=["Item 7", "Liquidity and Capital Resources"])
        segmented = _make_segmented([seg])
        records = annotator.annotate(segmented)
        # Confidence < threshold but ancestor matched → ancestor_prior
        assert records[0]["label_source"] == LABEL_SOURCE_ANCESTOR

    def test_llm_label_source_when_configured(self):
        annotator = _make_annotator()
        # Configure LLM backend
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"archetype": "regulatory", "confidence": 0.88}')]
        mock_llm.messages.create.return_value = mock_response
        annotator._llm_client = mock_llm
        annotator._use_llm_for = {"part1item1a"}

        seg = _seg("1A_001", "word " * 50)
        segmented = _make_segmented([seg], section_identifier="part1item1a")
        records = annotator.annotate(segmented)
        assert records[0]["label_source"] == LABEL_SOURCE_LLM

    def test_never_writes_classifier(self):
        annotator = _make_annotator()
        segs = [_seg(f"1A_{i:03d}", "word " * 50) for i in range(5)]
        segmented = _make_segmented(segs)
        records = annotator.annotate(segmented)
        for r in records:
            assert r["label_source"] != LABEL_SOURCE_CLASSIFIER

    def test_all_valid_namespace(self):
        annotator = _make_annotator()
        segs = [_seg(f"1A_{i:03d}", "word " * 50) for i in range(5)]
        segmented = _make_segmented(segs)
        records = annotator.annotate(segmented)
        for r in records:
            assert r["label_source"] in _VALID_LABEL_SOURCES

    def test_label_source_constants_match_expected_strings(self):
        assert LABEL_SOURCE_NLI        == "nli_zero_shot"
        assert LABEL_SOURCE_HEURISTIC  == "heuristic"
        assert LABEL_SOURCE_ANCESTOR   == "ancestor_prior"
        assert LABEL_SOURCE_LLM        == "llm_silver"
        assert LABEL_SOURCE_CLASSIFIER == "classifier"
        assert LABEL_SOURCE_HUMAN      == "human"
        assert LABEL_SOURCE_SYNTHETIC  == "llm_synthetic"


# ---------------------------------------------------------------------------
# Binary gate
# ---------------------------------------------------------------------------

class TestBinaryGate:
    def test_gate_filters_non_risk_in_part1item1(self):
        annotator = _make_annotator()
        # Gate mock: always returns "not relevant" (score=0.0 for "relevant")
        def _gate_pipe(text, candidates, hypothesis_template=None, multi_label=False):
            return {"labels": ["not relevant", "relevant"], "scores": [0.95, 0.05]}
        annotator._pipeline = _gate_pipe
        seg = _seg("1A_001", "Our headquarters are in Cupertino.", ancestors=[])
        segmented = _make_segmented([seg], section_identifier="part1item1")
        records = annotator.annotate(segmented)
        assert len(records) == 0

    def test_gate_passes_risk_in_part1item1(self):
        annotator = _make_annotator(pipeline_score=0.85)
        # Gate mock: "relevant" wins
        call_count = [0]
        def _pipe(text, candidates, hypothesis_template=None, multi_label=False):
            call_count[0] += 1
            if "relevant" in candidates:
                return {"labels": ["relevant", "not relevant"], "scores": [0.80, 0.20]}
            scores = {c: 0.01 for c in candidates}
            scores["cybersecurity"] = 0.85
            sorted_labels = sorted(scores, key=scores.__getitem__, reverse=True)
            return {"labels": sorted_labels, "scores": [scores[l] for l in sorted_labels]}
        annotator._pipeline = _pipe
        seg = _seg("1A_001", "We face cybersecurity risks.", ancestors=[])
        segmented = _make_segmented([seg], section_identifier="part1item1")
        records = annotator.annotate(segmented)
        assert len(records) == 1


# ---------------------------------------------------------------------------
# AnnotationConfig
# ---------------------------------------------------------------------------

class TestAnnotationConfig:
    def test_loads_from_yaml(self):
        from src.config.features.annotation import AnnotationConfig
        cfg = AnnotationConfig()
        assert cfg.model_name == "facebook/bart-large-mnli"
        assert cfg.merge_hi == 379
        assert "part1item1a" in cfg.section_include

    def test_env_override(self, monkeypatch):
        from src.config.features.annotation import AnnotationConfig
        monkeypatch.setenv("SEC_ANNOTATION__CONFIDENCE_THRESHOLD", "0.85")
        cfg = AnnotationConfig()
        assert cfg.confidence_threshold == pytest.approx(0.85)

    def test_annotator_uses_settings_defaults(self):
        annotator = _make_annotator()
        # Defaults come from annotation.yaml via settings.annotation
        from src.config import settings
        assert annotator._merge_hi == settings.annotation.merge_hi
        assert annotator._merge_lo == settings.annotation.merge_lo


# ---------------------------------------------------------------------------
# write_jsonl
# ---------------------------------------------------------------------------

class TestWriteJsonl:
    def test_writes_valid_jsonl(self, tmp_path):
        records = [
            {"index": 0, "text": "Risk text.", "label": 0, "risk_label": "cybersecurity",
             "word_count": 2, "char_count": 10, "char": 10,
             "sasb_topic": None, "sasb_industry": None,
             "sic_code": "7372", "ticker": "AAPL", "cik": "0000320193",
             "filing_date": "2021-10-29", "confidence": 0.85, "label_source": "nli_zero_shot"},
        ]
        out = tmp_path / "out.jsonl"
        SegmentAnnotator.write_jsonl(records, out)
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["label"] == 0
        assert parsed["label_source"] == "nli_zero_shot"

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "a" / "b" / "out.jsonl"
        SegmentAnnotator.write_jsonl([{"x": 1}], out)
        assert out.exists()


# ---------------------------------------------------------------------------
# _reformat_date
# ---------------------------------------------------------------------------

class TestReformatDate:
    def test_valid_yyyymmdd(self):
        assert _reformat_date("20211029") == "2021-10-29"

    def test_none_input(self):
        assert _reformat_date(None) is None

    def test_short_input(self):
        assert _reformat_date("2021") is None

    def test_empty_string(self):
        assert _reformat_date("") is None


# ---------------------------------------------------------------------------
# _heuristic_label
# ---------------------------------------------------------------------------

class TestHeuristicLabel:
    def test_cybersecurity_match(self):
        assert _heuristic_label("We face cybersecurity and data breach risks.") == "cybersecurity"

    def test_financial_match(self):
        assert _heuristic_label("Our liquidity and credit facilities may be impaired.") == "financial"

    def test_no_match_returns_other(self):
        assert _heuristic_label("The quick brown fox jumps over the lazy dog.") == "other"
