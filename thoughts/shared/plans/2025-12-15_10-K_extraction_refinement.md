---
date: 2025-12-15T12:00:00-05:00
researcher: gemini-cli
git_commit: current
branch: main
repository: SEC finetune
topic: "10-K Required Section Extraction Refinement"
tags: [plan, extractor, regex, 10-K]
status: ready_for_review
last_updated: 2025-12-15
last_updated_by: gemini-cli
related_research: thoughts/shared/plans/2025-12-03_19-49_extractor_fixes.md
---

# Plan: 10-K Required Section Extraction Refinement

**Date**: 2025-12-15
**Researcher**: gemini-cli
**Git Commit**: current
**Branch**: main

## Desired End State

After this plan is complete, the user will have:

* **Robust Item 7A Extraction**: The regex for "Item 7A. Quantitative and Qualitative Disclosures About Market Risk" will correctly match the full legal title, preventing extraction failures.
* **Verified Section Boundaries**: A dedicated test case will confirm that Item 7 does not leak into Item 7A, and Item 7A stops correctly at Item 8.
* **High Confidence in Required Sections**: The pipeline will be ready to reliably extract the four critical 10-K sections: Item 1, Item 1A, Item 7, and Item 7A.

### Key Discoveries (from Research)

* `src/preprocessing/constants.py:89` - The current regex `r'(?i)item\s*7\s*a\.?\s*market\s*risk'` expects "Market Risk" immediately after "7A", missing the "Quantitative and Qualitative Disclosures About" phrase.
* **Risk**: If the simple fallback `r'(?i)item\s*7a\.?'` is relied upon, it might be too broad or fail in non-standard formatting, leading to missing content or merged sections.

## What We're NOT Doing (Anti-Scope)

* **NOT** implementing a full pipeline script to run the extraction (this plan focuses on the *capability* to extract).
* **NOT** modifying the core `sec-parser` logic or tree construction.
* **NOT** adding regex patterns for every possible 10-K section, only the required ones (1, 1A, 7, 7A).

## Implementation Approach

We will target the specific regex weakness in `constants.py` and then immediately verify it with a new test case in the recently created `test_extractor.py`. This surgical approach minimizes risk while maximizing robustness for the specific goal.

---

## Phase 1: Robustify Regex Patterns

**Overview:** Update the regex patterns for `part2item7a` to handle the standard full title and variations.

### Changes Required:

**1. Update `SECTION_PATTERNS` for `part2item7a`**
**File:** `src/preprocessing/constants.py`
**Location:** ~Line 89 (inside `SECTION_PATTERNS`)

```python
    "part2item7a": [
        # Match standard full title (Quantitative and Qualitative...)
        r'(?i)item\s*7\s*a\.?\s*quantitative', 
        # Match short form or variations ending in Market Risk
        r'(?i)item\s*7\s*a\.?.*market\s*risk', 
        # Fallback (existing)
        r'(?i)item\s*7a\.?',
    ],
```

---

## Phase 2: Verification Test Case

**Overview:** Add a specific test case to ensure Item 7A is correctly identified and separated from Item 7.

### Changes Required:

**1. Add Item 7A Boundary Test**
**File:** `tests/preprocessing/test_extractor.py`
**Location:** Add to `TestBoundaryDetection` class

```python
    def test_is_next_section_matches_item_7a_full_title(self, extractor):
        """Verify Item 7A with full complex title is detected."""
        mock_node = MagicMock()
        mock_node.text = "Item 7A. Quantitative and Qualitative Disclosures About Market Risk"
        
        result = extractor._is_next_section(mock_node)
        assert result is True, "Should detect full Item 7A title"
```

---

## Success Criteria

### Automated Verification

- [ ] Regex patterns updated: `grep "quantitative" src/preprocessing/constants.py`
- [ ] New test passes: `pytest tests/preprocessing/test_extractor.py::TestBoundaryDetection::test_is_next_section_matches_item_7a_full_title -v`
- [ ] All extractor tests pass: `pytest tests/preprocessing/test_extractor.py -v`

### Manual Verification

- [ ] (Optional) Run extraction on a sample 10-K known to have the full Item 7A title and verify `part2item7a` is not None.

---

## File Summary

| File | Action | Lines (approx) | Description |
|------|--------|----------------|-------------|
| `src/preprocessing/constants.py` | Update | +4/-1 | Improve Item 7A regex |
| `tests/preprocessing/test_extractor.py` | Update | +8 | Add Item 7A test case |
| **Total** | | ~13 | |
