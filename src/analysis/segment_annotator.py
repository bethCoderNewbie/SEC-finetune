"""
SegmentAnnotator — transforms SegmentedRisks into flat JSONL training records.

Stage A: zero-shot classifier (facebook/bart-large-mnli)
Stage B: fine-tuned checkpoint swap — same interface, no schema change

Classification strategy:
  Layer 1 — Binary risk gate (part1item1 / part2item7 only)
  Layer 2 — Section-specific hypothesis templates
  Layer 3 — Ancestor heading score bonus (all 9 candidates always passed)
  Layer 4 — Section-specific confidence thresholds
  Layer 5 — Pluggable LLM backend (optional; inactive by default)

See research doc:
  thoughts/shared/research/2026-03-03_17-30-00_segment_annotator_jsonl_transform.md
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from src.config import settings
from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Archetype label map (PRD-002 §8) — module-level constant (OQ-A3 resolved)
# ---------------------------------------------------------------------------

ARCHETYPE_LABEL_MAP: ClassVar[Dict[str, int]] = {
    "cybersecurity":  0,
    "regulatory":     1,
    "financial":      2,
    "supply_chain":   3,
    "market":         4,
    "esg":            5,
    "macro":          6,
    "human_capital":  7,
    "other":          8,
}

ARCHETYPE_NAMES: List[str] = list(ARCHETYPE_LABEL_MAP.keys())

# ---------------------------------------------------------------------------
# label_source namespace — locked per ADR-015 (OQ-A9 resolved)
# Adding a new value without a superseding ADR is a bug.
# ---------------------------------------------------------------------------

LABEL_SOURCE_NLI        = "nli_zero_shot"   # BART Stage A; confidence >= section threshold
LABEL_SOURCE_HEURISTIC  = "heuristic"        # Keyword fallback; confidence < threshold
LABEL_SOURCE_ANCESTOR   = "ancestor_prior"   # Confidence < threshold; ancestor heading match
LABEL_SOURCE_LLM        = "llm_silver"       # LLM backend (llm_client configured)
LABEL_SOURCE_CLASSIFIER = "classifier"       # Stage B fine-tuned ONLY — not written here
LABEL_SOURCE_HUMAN      = "human"            # IAA annotator — not written here
LABEL_SOURCE_SYNTHETIC  = "llm_synthetic"    # Synthesis script — not written here

_VALID_LABEL_SOURCES: frozenset = frozenset({
    LABEL_SOURCE_NLI,
    LABEL_SOURCE_HEURISTIC,
    LABEL_SOURCE_ANCESTOR,
    LABEL_SOURCE_LLM,
    LABEL_SOURCE_CLASSIFIER,
    LABEL_SOURCE_HUMAN,
    LABEL_SOURCE_SYNTHETIC,
})

# ---------------------------------------------------------------------------
# Section-specific NLI hypothesis templates (§4.4.2)
# ---------------------------------------------------------------------------

_HYPOTHESIS_TEMPLATES: Dict[str, str] = {
    "part1item1a": "This text describes a risk related to {archetype}.",
    "part1item1c": "This text describes a risk related to {archetype}.",
    "part1item1":  (
        "This business description reveals a dependency, concentration, "
        "or structural exposure related to {archetype}."
    ),
    "part2item7":  (
        "This management discussion describes the financial or operational "
        "impact of, or ongoing exposure to, {archetype}-related factors."
    ),
    "part2item7a": (
        "This market risk disclosure describes quantitative exposure to {archetype}."
    ),
    "_default":    "This text describes a risk related to {archetype}.",
}

# ---------------------------------------------------------------------------
# Ancestor heading → archetype prior (§4.4.3 / OQ-A18)
# Keys are lowercase; matched against ancestors[-1].lower()
# ---------------------------------------------------------------------------

_ANCESTOR_ARCHETYPE_PRIOR: Dict[str, str] = {
    "liquidity and capital resources": "financial",
    "market risk":                     "market",
    "competition":                     "market",
    "supply chain":                    "supply_chain",
    "cybersecurity":                   "cybersecurity",
    "regulatory":                      "regulatory",
    "human capital":                   "human_capital",
    "environmental":                   "esg",
    "climate":                         "esg",
    "critical accounting":             "financial",
}

# ---------------------------------------------------------------------------
# Per-section confidence thresholds (§4.4.4)
# Implicit-language sections use lower values.
# ---------------------------------------------------------------------------

_SECTION_CONFIDENCE_THRESHOLDS: Dict[str, float] = {
    "part1item1a": 0.70,
    "part1item1c": 0.70,
    "part2item7a": 0.65,
    "part2item7":  0.60,
    "part1item1":  0.55,
    "_default":    0.70,
}

# ---------------------------------------------------------------------------
# Heuristic keyword fallback (§4.5)
# Used when NLI confidence < threshold and no ancestor prior matches.
# ---------------------------------------------------------------------------

_HEURISTIC_KEYWORDS: Dict[str, List[str]] = {
    "cybersecurity":  ["cybersecurity", "data breach", "ransomware", "gdpr", "unauthorized access"],
    "regulatory":     ["regulatory", "compliance", "sec", "litigation", "enforcement", "cftc"],
    "financial":      ["liquidity", "credit", "default", "interest rate", "refinancing", "debt"],
    "supply_chain":   ["supply chain", "supplier", "logistics", "procurement", "sourcing"],
    "market":         ["competition", "market share", "pricing", "demand", "commodity"],
    "esg":            ["environmental", "climate", "greenhouse", "esg", "emissions", "sustainability"],
    "macro":          ["inflation", "recession", "gdp", "federal reserve", "foreign exchange", "tariff"],
    "human_capital":  ["workforce", "talent", "retention", "labor", "union", "employee"],
    "other":          [],
}

# Sections where the binary risk gate is applied (§4.4.1).
# All other sections are considered fully risk-relevant and skip the gate.
_BINARY_GATE_SECTIONS: frozenset = frozenset({"part1item1", "part2item7"})

# Hard-excluded sections — never annotated (§4.6 revised section policy)
_HARD_EXCLUDED_SECTIONS: frozenset = frozenset({"part1item1b", "part2item8"})


# ---------------------------------------------------------------------------
# SegmentAnnotator
# ---------------------------------------------------------------------------

class SegmentAnnotator:
    """
    Transforms SegmentedRisks into flat JSONL records matching PRD-002 §8 schema.

    Usage:
        annotator = SegmentAnnotator()
        count = annotator.annotate_run_dir(
            run_dir=Path("data/processed/20260303_160207_preprocessing_3bc89d7"),
            output_path=Path("data/processed/annotation/labeled.jsonl"),
        )
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        taxonomy_manager: Optional[Any] = None,
        archetype_yaml_path: Optional[Path] = None,
        confidence_threshold: Optional[float] = None,
        binary_gate_threshold: Optional[float] = None,
        merge_lo: Optional[int] = None,
        merge_hi: Optional[int] = None,
        device: Optional[int] = None,
        llm_client: Optional[Any] = None,
        use_llm_for_sections: Tuple[str, ...] = (),
    ) -> None:
        cfg = settings.annotation
        self._model_name         = model_name          if model_name          is not None else cfg.model_name
        self._confidence_thresh  = confidence_threshold if confidence_threshold is not None else cfg.confidence_threshold
        self._gate_thresh        = binary_gate_threshold if binary_gate_threshold is not None else cfg.binary_gate_threshold
        self._merge_lo           = merge_lo             if merge_lo             is not None else cfg.merge_lo
        self._merge_hi           = merge_hi             if merge_hi             is not None else cfg.merge_hi
        self._device             = device               if device               is not None else cfg.device
        self._llm_client         = llm_client
        self._use_llm_for        = set(use_llm_for_sections)

        # Lazy-import to avoid loading torch at module import time
        from transformers import pipeline as hf_pipeline  # type: ignore

        logger.info("Loading NLI pipeline: %s (device=%d)", self._model_name, self._device)
        self._pipeline = hf_pipeline(
            "zero-shot-classification",
            model=self._model_name,
            device=self._device,
        )
        self._tokenizer = self._pipeline.tokenizer

        # TaxonomyManager — graceful no-op when sasb_sics_mapping.json absent
        if taxonomy_manager is None:
            from src.analysis.taxonomies.taxonomy_manager import TaxonomyManager  # type: ignore
            taxonomy_manager = TaxonomyManager()
        self._taxonomy = taxonomy_manager

        # archetype → sasb crosswalk (Option A); null when file absent
        resolved_yaml = archetype_yaml_path
        if resolved_yaml is None:
            resolved_yaml = settings.paths.taxonomies_dir / "archetype_to_sasb.yaml"
        self._crosswalk: Optional[Dict[str, Dict[str, str]]] = None
        if resolved_yaml.exists():
            import yaml  # type: ignore
            with open(resolved_yaml) as fh:
                self._crosswalk = yaml.safe_load(fh)
            logger.info("Loaded archetype_to_sasb crosswalk from %s", resolved_yaml)
        else:
            logger.debug("archetype_to_sasb.yaml absent — sasb_topic will be null (US-030)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def annotate(self, segmented: SegmentedRisks) -> List[Dict[str, Any]]:
        """
        Merge short segments by ancestors, classify each, return flat records.

        Args:
            segmented: Loaded SegmentedRisks (filed_as_of_date must be non-None for
                       valid filing_date output — apply B-5 fix first).

        Returns:
            List of flat dicts matching PRD-002 §8 Phase 2 schema.
        """
        section_id    = segmented.section_identifier or "_default"
        sasb_industry = self._taxonomy.get_industry_for_sic(segmented.sic_code)
        filing_date   = _reformat_date(segmented.filed_as_of_date)

        merged = self._merge_by_ancestors(segmented.segments, self._merge_lo, self._merge_hi)
        records: List[Dict[str, Any]] = []
        index = 0

        section_threshold = _SECTION_CONFIDENCE_THRESHOLDS.get(
            section_id, _SECTION_CONFIDENCE_THRESHOLDS["_default"]
        )
        template = _HYPOTHESIS_TEMPLATES.get(section_id, _HYPOTHESIS_TEMPLATES["_default"])

        for seg in merged:
            # Layer 1: binary risk gate (part1item1 / part2item7 only)
            if section_id in _BINARY_GATE_SECTIONS:
                if not self._is_risk_relevant(seg.text, section_id, self._pipeline, self._gate_thresh):
                    continue

            # Classify
            top_archetype, confidence, ancestor_matched = self._classify_segment(
                seg, section_id, template, section_threshold
            )

            # label_source (ADR-015)
            if section_id in self._use_llm_for and self._llm_client is not None:
                top_archetype, confidence = self._classify_with_llm(seg, section_id)
                label_source = LABEL_SOURCE_LLM
            elif confidence >= section_threshold:
                label_source = LABEL_SOURCE_NLI
            elif ancestor_matched:
                label_source = LABEL_SOURCE_ANCESTOR
            else:
                label_source = LABEL_SOURCE_HEURISTIC

            label      = ARCHETYPE_LABEL_MAP[top_archetype]
            sasb_topic = self._crosswalk_sasb(top_archetype, sasb_industry)

            records.append({
                "index":        index,
                "text":         seg.text,
                "word_count":   seg.word_count,
                "char_count":   seg.char_count,
                "label":        label,
                "risk_label":   top_archetype,
                "sasb_topic":   sasb_topic,
                "sasb_industry": sasb_industry,
                "sic_code":     segmented.sic_code,
                "ticker":       segmented.ticker,
                "cik":          segmented.cik,
                "filing_date":  filing_date,
                "confidence":   round(confidence, 4),
                "label_source": label_source,
            })
            index += 1

        return records

    def annotate_run_dir(
        self,
        run_dir: Path,
        output_path: Path,
        section_include: Optional[List[str]] = None,
        part2item7_subsection_filter: Optional[List[str]] = None,
    ) -> int:
        """
        Annotate all *_segmented.json files in run_dir, write to output_path as JSONL.

        Args:
            run_dir:                     Stamped preprocessing run directory.
            output_path:                 Destination JSONL file path.
            section_include:             Section identifiers to include. Defaults to
                                         settings.annotation.section_include.
            part2item7_subsection_filter: When part2item7 is included, only retain
                                         chunks whose ancestors[-1] matches an entry
                                         here. None = include all (not recommended).

        Returns:
            Total record count written.
        """
        if section_include is None:
            section_include = list(settings.annotation.section_include)

        # Enforce hard excludes
        invalid = set(section_include) & _HARD_EXCLUDED_SECTIONS
        if invalid:
            raise ValueError(
                f"Sections {invalid} are hard-excluded and cannot be annotated. "
                "Remove them from section_include."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        total = 0

        with output_path.open("w", encoding="utf-8") as fh:
            for json_path in sorted(run_dir.glob("*_segmented.json")):
                segmented = SegmentedRisks.load_from_json(json_path)
                sid = segmented.section_identifier or ""
                if sid not in section_include:
                    continue

                # part2item7 subsection filter
                if sid == "part2item7" and part2item7_subsection_filter is not None:
                    filter_lower = {s.lower() for s in part2item7_subsection_filter}
                    segmented = _filter_by_ancestor(segmented, filter_lower)

                records = self.annotate(segmented)
                for rec in records:
                    fh.write(json.dumps(rec) + "\n")
                total += len(records)
                logger.debug("Annotated %s: %d records", json_path.name, len(records))

        logger.info("annotate_run_dir complete: %d records → %s", total, output_path)
        return total

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_by_ancestors(
        segments: List[RiskSegment],
        merge_lo: int = 200,
        merge_hi: int = 379,
    ) -> List[RiskSegment]:
        """
        Group consecutive segments with identical ancestors and greedily merge
        into segments targeting [merge_lo, merge_hi] words (§4.6 algorithm).

        Segments already >= merge_lo pass through unchanged.
        Segments already > merge_hi pass through unchanged (no truncation).
        """
        if not segments:
            return []

        result: List[RiskSegment] = []
        i = 0
        while i < len(segments):
            seg = segments[i]

            # Pass through: already at or above target
            if seg.word_count >= merge_lo:
                result.append(seg)
                i += 1
                continue

            # ancestors=[] → singleton run per spec (§4.6 / ADR-014 cover-page nodes)
            if not seg.ancestors:
                result.append(seg)
                i += 1
                continue

            # Collect run of same-ancestors segments starting at i
            run: List[RiskSegment] = [seg]
            j = i + 1
            while j < len(segments) and segments[j].ancestors == seg.ancestors:
                run.append(segments[j])
                j += 1

            # If singleton run and below merge_lo: emit as-is (best effort)
            if len(run) == 1:
                result.append(seg)
                i += 1
                continue

            # Greedy forward accumulation within the run
            acc_text:  List[str] = []
            acc_words: int = 0
            acc_chars: int = 0
            start_chunk_id     = run[0].chunk_id
            start_parent_sub   = run[0].parent_subsection
            start_ancestors    = run[0].ancestors

            for s in run:
                if acc_words + s.word_count > merge_hi:
                    # Flush current accumulator
                    if acc_words > 0:
                        result.append(_make_merged_segment(
                            acc_text, acc_words, acc_chars,
                            start_chunk_id, s.chunk_id,
                            start_parent_sub, start_ancestors,
                        ))
                    # Start fresh with s
                    acc_text  = [s.text]
                    acc_words = s.word_count
                    acc_chars = s.char_count
                    start_chunk_id   = s.chunk_id
                    start_parent_sub = s.parent_subsection
                    start_ancestors  = s.ancestors
                else:
                    acc_text.append(s.text)
                    acc_words += s.word_count
                    acc_chars += s.char_count

                if acc_words >= merge_lo:
                    result.append(_make_merged_segment(
                        acc_text, acc_words, acc_chars,
                        start_chunk_id, s.chunk_id,
                        start_parent_sub, start_ancestors,
                    ))
                    acc_text, acc_words, acc_chars = [], 0, 0
                    start_chunk_id = ""

            # Flush remaining
            if acc_words > 0:
                last_chunk_id = run[-1].chunk_id
                result.append(_make_merged_segment(
                    acc_text, acc_words, acc_chars,
                    start_chunk_id, last_chunk_id,
                    start_parent_sub, start_ancestors,
                ))

            i = j  # advance past the run

        return result

    @staticmethod
    def _is_risk_relevant(
        text: str,
        section_id: str,
        pipeline: Any,
        gate_threshold: float = 0.5,
    ) -> bool:
        """
        Binary pre-classification gate (§4.4.1).
        Always returns True for sections not in _BINARY_GATE_SECTIONS.
        """
        if section_id not in _BINARY_GATE_SECTIONS:
            return True
        hypothesis = (
            "This text describes a risk, vulnerability, dependency, or adverse event "
            "that could affect the company's operations or finances."
        )
        result = pipeline(text, ["relevant", "not relevant"], hypothesis_template=hypothesis)
        scores = dict(zip(result["labels"], result["scores"]))
        return scores.get("relevant", 0.0) >= gate_threshold

    @staticmethod
    def _apply_ancestor_score_bonus(
        scores: Dict[str, float],
        ancestors: List[str],
        ancestor_prior: Dict[str, str],
        bonus: float = 0.05,
    ) -> Tuple[Dict[str, float], bool]:
        """
        Apply a score bonus to the ancestor-implied archetype (OQ-A18 option c).
        All 9 candidates are always passed — correct label is never excluded.

        Returns:
            (updated_scores, ancestor_matched)
        """
        if not ancestors:
            return scores, False
        key = ancestors[-1].lower()
        # Match substring: "Liquidity and Capital Resources" → key contains "liquidity"
        matched_archetype = None
        for heading, archetype in ancestor_prior.items():
            if heading in key:
                matched_archetype = archetype
                break
        if matched_archetype is None:
            return scores, False
        updated = dict(scores)
        if matched_archetype in updated:
            updated[matched_archetype] = min(1.0, updated[matched_archetype] + bonus)
        return updated, True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_segment(
        self,
        seg: RiskSegment,
        section_id: str,
        template: str,
        section_threshold: float,
    ) -> Tuple[str, float, bool]:
        """
        Run NLI classification with ancestor score bonus.

        Returns:
            (top_archetype, confidence, ancestor_prior_matched)
        """
        top_archetype, confidence = self._classify_archetype(seg.text, template, seg.ancestors)
        # Check whether ancestor matching happened (for label_source routing)
        if seg.ancestors:
            key = seg.ancestors[-1].lower()
            ancestor_matched = any(h in key for h in _ANCESTOR_ARCHETYPE_PRIOR)
        else:
            ancestor_matched = False

        # If below threshold and no ancestor match, fall back to heuristic
        if confidence < section_threshold and not ancestor_matched:
            top_archetype = _heuristic_label(seg.text)

        return top_archetype, confidence, ancestor_matched

    def _classify_archetype(
        self,
        text: str,
        template: str,
        ancestors: List[str],
    ) -> Tuple[str, float]:
        """
        Call NLI pipeline with token-count truncation and ancestor score bonus.
        Always passes all 9 ARCHETYPE_NAMES as candidates (OQ-A18 option c).
        """
        # Token-count truncation (fixes C-10 / B-8): truncate to model max_length - 2
        max_tokens = self._tokenizer.model_max_length - 2
        tokens = self._tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) > max_tokens:
            text = self._tokenizer.decode(tokens[:max_tokens], skip_special_tokens=True)

        result = self._pipeline(
            text,
            ARCHETYPE_NAMES,
            hypothesis_template=template,
            multi_label=False,
        )
        raw_scores = dict(zip(result["labels"], result["scores"]))

        # Apply ancestor score bonus (returns unchanged scores if no match)
        bonused_scores, _ = self._apply_ancestor_score_bonus(
            raw_scores, ancestors, _ANCESTOR_ARCHETYPE_PRIOR
        )

        top_archetype = max(bonused_scores, key=bonused_scores.__getitem__)
        confidence    = bonused_scores[top_archetype]
        return top_archetype, confidence

    def _classify_with_llm(
        self,
        seg: RiskSegment,
        section_id: str,
    ) -> Tuple[str, float]:
        """
        LLM backend classification (§4.4.5). Activated when llm_client is set
        and section_id is in use_llm_for_sections.

        Returns:
            (top_archetype, confidence)
        """
        section_name_map = {
            "part1item1":  "Business Overview (Item 1)",
            "part1item1a": "Risk Factors (Item 1A)",
            "part1item1c": "Cybersecurity (Item 1C)",
            "part2item7":  "MD&A (Item 7)",
            "part2item7a": "Quantitative Market Risk (Item 7A)",
        }
        section_name  = section_name_map.get(section_id, section_id)
        archetype_list = ", ".join(ARCHETYPE_NAMES)
        ancestor_ctx   = seg.ancestors[-1] if seg.ancestors else "Unknown"

        prompt = (
            f"Classify the following text from a 10-K {section_name} into the most applicable "
            f"risk archetype, or \"other\" if no risk is implied.\n"
            f"Return JSON only: {{\"archetype\": str, \"confidence\": float}}\n"
            f"Archetypes: {archetype_list}\n"
            f"Context: This text appears under the heading: \"{ancestor_ctx}\"\n"
            f"Text: {seg.text}"
        )

        try:
            response = self._llm_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=64,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = json.loads(raw)
            archetype  = parsed.get("archetype", "other")
            confidence = float(parsed.get("confidence", 0.5))
            if archetype not in ARCHETYPE_LABEL_MAP:
                archetype = "other"
            return archetype, confidence
        except Exception as exc:
            logger.warning("LLM classification failed (%s), falling back to NLI", exc)
            template = _HYPOTHESIS_TEMPLATES.get(section_id, _HYPOTHESIS_TEMPLATES["_default"])
            return self._classify_archetype(seg.text, template, seg.ancestors)

    def _crosswalk_sasb(
        self,
        archetype: str,
        sasb_industry: Optional[str],
    ) -> Optional[str]:
        """
        Look up sasb_topic via archetype_to_sasb.yaml crosswalk (Option A).
        Returns None when crosswalk or industry is absent.
        """
        if self._crosswalk is None or sasb_industry is None:
            return None
        return self._crosswalk.get(archetype, {}).get(sasb_industry)

    @staticmethod
    def write_jsonl(records: List[Dict[str, Any]], output_path: Path) -> None:
        """Write records to JSONL, one JSON object per line."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _reformat_date(yyyymmdd: Optional[str]) -> Optional[str]:
    """Convert YYYYMMDD to YYYY-MM-DD. Returns None if input is None or malformed."""
    if not yyyymmdd or len(yyyymmdd) != 8:
        return None
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _heuristic_label(text: str) -> str:
    """
    Keyword-based fallback label (§4.5).
    Returns the archetype with the most keyword matches, or 'other' if none match.
    """
    text_lower = text.lower()
    best_archetype = "other"
    best_count = 0
    for archetype, keywords in _HEURISTIC_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_archetype = archetype
    return best_archetype


def _make_merged_segment(
    texts: List[str],
    word_count: int,
    char_count: int,
    first_chunk_id: str,
    last_chunk_id: str,
    parent_subsection: Optional[str],
    ancestors: List[str],
) -> RiskSegment:
    """Build a merged RiskSegment from accumulated text chunks."""
    joined = " ".join(texts)
    if len(texts) == 1 or first_chunk_id == last_chunk_id:
        chunk_id = first_chunk_id
    else:
        chunk_id = f"{first_chunk_id}+{last_chunk_id}"
    return RiskSegment(
        chunk_id=chunk_id,
        parent_subsection=parent_subsection,
        ancestors=ancestors,
        text=joined,
        word_count=word_count,
        char_count=char_count,
    )


def _filter_by_ancestor(
    segmented: SegmentedRisks,
    filter_lower: set,
) -> SegmentedRisks:
    """Return a new SegmentedRisks with chunks filtered by ancestors[-1] match."""
    kept = [
        s for s in segmented.segments
        if s.ancestors and s.ancestors[-1].lower() in filter_lower
    ]
    # Return a shallow copy with filtered segments
    return segmented.model_copy(update={"segments": kept, "total_segments": len(kept)})
