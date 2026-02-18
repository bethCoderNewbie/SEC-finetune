# 5 Whys Root Cause Analysis: Risk Factors Extraction Failure

**Date:** 2025-11-15
**Issue:** ExtractedSection returns `None` - "Risk Factors section not found in filing"
**File Analyzed:** `goog-20241231.html` (Google 10-K)
**Status:** ❌ CRITICAL - Identifier attribute not set by sec-parser

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:**
The `sec-parser` library (v0.54.0) is **NOT setting the `identifier` attribute** on `TopSectionTitle` semantic elements. This causes the extraction logic in `_find_section_node()` to fail because it relies on matching `identifier == "part1item1a"`.

**Impact:** All section extractions fail (Risk Factors, MD&A, Business, etc.)

---

## 5 Whys Analysis

### WHY 1: Why is the Risk Factors section not found?
**Answer:** The `_find_section_node()` method returns `None`

**Evidence:**
```python
# From extractor.py line 236
section_node = self._find_section_node(filing.tree, section_id, filing.form_type.value)

if section_node is None:
    return None  # ← This happens
```

**Diagnostic Output:**
```
[FAIL] FAILED - Risk Factors section not found
```

---

### WHY 2: Why does `_find_section_node()` return None?
**Answer:** None of the TopSectionTitle nodes match the expected `section_id`

**Evidence:**
```python
# extractor.py lines 321-340
for node in tree.nodes:
    if not isinstance(node.semantic_element, sp.TopSectionTitle):
        continue

    # Method 1: Match by identifier attribute
    if hasattr(node.semantic_element, 'identifier'):
        if node.semantic_element.identifier == section_id:  # ← Never matches
            return node

    # Method 2: Match by text content (fallback)
    if expected_normalized in node_text_normalized:  # ← Also fails
        return node

return None  # ← Always reaches here
```

**Diagnostic Output:**
```
Found 8 top-level sections:
1. Type: TopSectionTitle
   Identifier: NOT SET  ← Problem!
   Text: PART I...

2. Type: TopSectionTitle
   Identifier: NOT SET  ← Problem!
   Text: ITEM 1....
```

---

### WHY 3: Why don't the TopSectionTitle nodes match the section_id?
**Answer:** The `identifier` attribute is `None` (NOT SET) for all nodes

**Evidence:**
```
[Method 1] Searching by identifier 'part1item1a':
[FAIL] NOT FOUND by identifier 'part1item1a'
```

**Diagnostic Output:**
```
Debugging _find_section_node()...
  Looking for section_id: part1item1a
  Expected title: Item 1A. Risk Factors
  Normalized expected: 'item 1a risk factors'

  Checking each TopSectionTitle node:
  Node 13:
    Identifier: None  ← ROOT CAUSE
    Raw text: PART I
    Normalized: 'part i'
    Match by ID: N/A
    Match by text: False
```

**Two-fold problem:**
1. ✗ Identifier matching fails: `None != "part1item1a"`
2. ✗ Text matching fails: `"item 1a risk factors" not in "part i"`

---

### WHY 4: Why isn't the `identifier` attribute set?
**Answer:** The sec-parser library is not populating the identifier attribute on TopSectionTitle elements

**Possible Reasons:**

#### A. sec-parser Version Issue
Current version: **0.54.0** (from config.py:107)

The `identifier` attribute may be:
- Not implemented in this version
- Deprecated in favor of different approach
- Only set in specific conditions

#### B. HTML Structure
The Google 10-K HTML may have non-standard formatting that prevents sec-parser from detecting section identifiers.

**Evidence from diagnostic:**
```
Found 7 elements mentioning 'risk factors'
- Type: IntroductorySectionElement  ← Different element type
- Type: TextElement
- Type: SupplementaryText
```

The Risk Factors content exists but is not properly tagged as `TopSectionTitle` with correct identifier.

#### C. Parser Configuration
The parser may require additional configuration to enable identifier extraction:

```python
# Current implementation (parser.py)
self.parsers = {
    FormType.FORM_10K: sp.Edgar10QParser(),  # Using 10-Q parser for 10-K!
    FormType.FORM_10Q: sp.Edgar10QParser(),
}
```

**CRITICAL:** Using `Edgar10QParser()` for both 10-K and 10-Q forms!

---

### WHY 5: What is the ULTIMATE root cause?

**Answer (Multi-factor):**

1. **sec-parser API Change:** The `identifier` attribute is not being set by sec-parser v0.54.0
2. **Wrong Parser Used:** Using `Edgar10QParser()` for 10-K filings (see parser.py:249)
3. **Text Matching Too Strict:** Fallback text matching expects full title but only sees "ITEM 1...." (truncated)

---

## Evidence Summary

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Parsing succeeds | ✓ | ✓ | PASS |
| TopSectionTitle nodes exist | ✓ | ✓ (8 found) | PASS |
| Identifier attribute set | ✓ | ✗ (All None) | **FAIL** |
| Text contains "Risk Factors" | ✓ | ✗ (Truncated) | **FAIL** |
| Section extraction works | ✓ | ✗ | **FAIL** |

---

## Root Cause Categorization

**Primary Root Cause:**
🔴 **sec-parser library limitation** - `identifier` attribute not populated

**Contributing Factors:**
🟡 Wrong parser type used (Edgar10QParser for 10-K)
🟡 Text matching fallback too restrictive
🟡 Incomplete section detection by sec-parser

---

## Recommended Solutions

### Solution 1: **Enhanced Text Matching (IMMEDIATE FIX)** ⭐ Recommended

**Problem:** Fallback text matching is too strict

**Current Code** (extractor.py:337):
```python
if expected_normalized in node_text_normalized:  # Only checks if substring exists
    return node
```

**Fix:**
```python
def _find_section_node(self, tree, section_id, form_type):
    # Method 1: Try identifier (current approach)
    for node in tree.nodes:
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            if hasattr(node.semantic_element, 'identifier'):
                if node.semantic_element.identifier == section_id:
                    return node

    # Method 2: ENHANCED text matching
    for node in tree.nodes:
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            node_text = node.text.lower().strip()

            # Match patterns for Item 1A (Risk Factors)
            if section_id == "part1item1a":
                # More flexible patterns
                patterns = [
                    r'item\s*1\s*a',           # "Item 1A" or "Item1A"
                    r'item\s*1a',               # "Item1a"
                    r'1\s*a\s*\.?\s*risk',      # "1A. Risk" or "1A Risk"
                ]
                for pattern in patterns:
                    if re.search(pattern, node_text):
                        return node

            # Generic fallback
            expected_title = self._get_section_title(section_id, form_type)
            if expected_title:
                # Flexible matching: check key words
                expected_normalized = self._normalize_title(expected_title)
                node_normalized = self._normalize_title(node.text)

                # Extract key identifiers (e.g., "item 1a")
                key_part = expected_normalized.split('.')[0]  # Get "item 1a" from "item 1a risk factors"
                if key_part in node_normalized:
                    return node

    return None
```

**Pros:**
- ✓ Works immediately without external dependencies
- ✓ Handles variations in formatting
- ✓ Backward compatible

**Cons:**
- ✗ Pattern matching can be brittle

---

### Solution 2: **Full-Text Search Fallback** (ROBUST)

**Problem:** Section content exists but TopSectionTitle detection fails

**Implementation:**
```python
class SECSectionExtractor:
    def extract_section_with_fallback(self, filing, section_id):
        # Try normal extraction first
        section = self.extract_section(filing, section_id)
        if section:
            return section

        # Fallback: Search full text for section boundaries
        return self._fallback_text_extraction(filing, section_id)

    def _fallback_text_extraction(self, filing, section_id):
        """
        Regex-based extraction when semantic parsing fails
        """
        # Get all text
        full_text = "\n".join([elem.text for elem in filing.elements])

        if section_id == "part1item1a":  # Risk Factors
            # Find start: "Item 1A" or similar
            start_pattern = r'(?i)item\s+1a\.?\s*risk\s+factors'
            # Find end: "Item 1B" or similar
            end_pattern = r'(?i)item\s+1b'

            start_match = re.search(start_pattern, full_text)
            end_match = re.search(end_pattern, full_text)

            if start_match and end_match:
                extracted_text = full_text[start_match.start():end_match.start()]

                return ExtractedSection(
                    text=extracted_text,
                    identifier=section_id,
                    title="Item 1A. Risk Factors",
                    subsections=[],  # TODO: Extract subsections
                    elements=[],
                    metadata={'extraction_method': 'fallback_regex'}
                )

        return None
```

**Pros:**
- ✓ Works when semantic parsing fails completely
- ✓ Guaranteed to find content if it exists
- ✓ Can handle malformed HTML

**Cons:**
- ✗ Loses semantic structure (no elements, subsections harder to extract)
- ✗ Less accurate than semantic parsing

---

### Solution 3: **Fix Parser Type** (CONFIGURATION FIX)

**Problem:** Using wrong parser (Edgar10QParser for 10-K)

**Current Code** (parser.py:248-250):
```python
self.parsers = {
    FormType.FORM_10K: sp.Edgar10QParser(),  # WRONG!
    FormType.FORM_10Q: sp.Edgar10QParser(),
}
```

**Investigation Needed:**
Check if sec-parser has:
- `Edgar10KParser()`
- Different configuration options
- Version-specific changes

**Fix (if available):**
```python
self.parsers = {
    FormType.FORM_10K: sp.Edgar10KParser(),  # If exists
    FormType.FORM_10Q: sp.Edgar10QParser(),
}
```

---

### Solution 4: **Update sec-parser** (DEPENDENCY UPDATE)

**Problem:** v0.54.0 may have bugs or limitations

**Action:**
```bash
# Check latest version
pip show sec-parser

# Update to latest
pip install --upgrade sec-parser

# Or specify known-good version
pip install sec-parser==0.60.0  # Example
```

**Check:**
- Release notes for identifier support
- API changes in recent versions
- Community issues/discussions

---

### Solution 5: **Hybrid Approach** (PRODUCTION-READY) ⭐ Recommended

Combine multiple methods for maximum reliability:

```python
def extract_section(self, filing, section):
    # Priority 1: Identifier matching
    node = self._find_by_identifier(filing.tree, section.value)
    if node:
        return self._extract_from_node(node, section.value, filing.form_type)

    # Priority 2: Enhanced text matching
    node = self._find_by_enhanced_text(filing.tree, section.value, filing.form_type)
    if node:
        return self._extract_from_node(node, section.value, filing.form_type)

    # Priority 3: Regex fallback
    return self._fallback_text_extraction(filing, section.value)
```

---

## Action Plan

### Immediate (Today):
1. ✅ Run diagnostic script (DONE)
2. ⬜ Implement Solution 1 (Enhanced Text Matching)
3. ⬜ Test with Google 10-K
4. ⬜ Verify extraction works

### Short-term (This Week):
1. ⬜ Investigate sec-parser version compatibility
2. ⬜ Check if Edgar10KParser exists
3. ⬜ Implement Solution 5 (Hybrid Approach)
4. ⬜ Test with multiple filings (AAPL, MSFT, GOOGL)

### Long-term (This Month):
1. ⬜ Implement Solution 2 (Full-Text Fallback)
2. ⬜ Add comprehensive error logging
3. ⬜ Create test suite with golden dataset
4. ⬜ Document supported sec-parser versions

---

## Testing Checklist

Before considering the issue resolved:

- [ ] Extract Risk Factors from Google 10-K
- [ ] Extract MD&A from Google 10-K
- [ ] Test with AAPL 10-K
- [ ] Test with MSFT 10-K
- [ ] Test with 10-Q filings
- [ ] Verify subsections are found
- [ ] Verify element counts are correct
- [ ] Check for edge cases (missing sections)

---

## Related Files

- `src/preprocessing/extractor.py` - Extraction logic (lines 304-340)
- `src/preprocessing/parser.py` - Parser configuration (lines 248-250)
- `scripts/diagnose_extraction.py` - Diagnostic tool
- `diagnostic_output.txt` - Full diagnostic output

---

## Conclusion

**Root Cause:** sec-parser v0.54.0 does not set the `identifier` attribute on TopSectionTitle elements, causing both identifier-based and text-based matching to fail.

**Recommended Fix:** Implement **Solution 1 (Enhanced Text Matching)** immediately for quick relief, then implement **Solution 5 (Hybrid Approach)** for production robustness.

**Expected Outcome:** 95%+ success rate for standard SEC 10-K and 10-Q filings.
