# Plan: Fix Curly Quotes Normalization in TextCleaner

## Desired End State
After this fix is complete:
* TextCleaner normalizes all curly/smart quotes to straight ASCII quotes
* Left double quote (`"` U+201C) → straight double quote (`"` U+0022)
* Right double quote (`"` U+201D) → straight double quote (`"` U+0022)
* Left single quote (`'` U+2018) → straight single quote/apostrophe (`'` U+0027)
* Right single quote (`'` U+2019) → straight single quote/apostrophe (`'` U+0027)
* The xfailed test `test_curly_quotes_normalized` passes

### Key Discoveries
* **Root Cause**: `cleaning.py:190-192` - The current code replaces straight quotes with straight quotes (a no-op)
* The code looks like it handles curly quotes but uses ASCII `"` and `'` instead of Unicode curly quotes
* **Evidence**: Line 191 shows `text.replace('"', '"')` - both are ASCII U+0022, not Unicode curly quotes
* **Test Location**: `tests/preprocessing/test_cleaner.py:113-125` - Currently marked xfail
* **Real Data Impact**: 252 curly quote instances found in cleaned SEC filings (from test output)

## What We're NOT Doing
* Not handling other Unicode quote variants (e.g., guillemets «», Japanese quotes 「」)
* Not changing the public API of TextCleaner
* Not modifying how other normalization methods work
* Not adding new configuration options for quote handling

## Implementation Approach
Single-phase fix: Update `_normalize_punctuation()` to use correct Unicode escape sequences for curly quotes, then remove the xfail marker from the test.

---

## Phase 1: Fix Curly Quote Normalization

**Overview:** Replace the incorrect ASCII quote replacement with proper Unicode curly quote handling.

### Changes Required:

**1. TextCleaner._normalize_punctuation()**
**File:** `src/preprocessing/cleaning.py` (modification at lines 190-192)
**Changes:** Use Unicode escape sequences to properly identify and replace curly quotes

**Current (broken):**
```python
def _normalize_punctuation(self, text: str) -> str:
    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')  # No-op: ASCII to ASCII
    text = text.replace(''', "'").replace(''', "'")  # No-op: ASCII to ASCII
```

**Fixed:**
```python
def _normalize_punctuation(self, text: str) -> str:
    # Normalize curly/smart quotes to straight ASCII quotes
    # Double quotes: " (U+201C) and " (U+201D) → " (U+0022)
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    # Single quotes/apostrophes: ' (U+2018) and ' (U+2019) → ' (U+0027)
    text = text.replace('\u2018', "'").replace('\u2019', "'")
```

**2. Remove xfail marker from test**
**File:** `tests/preprocessing/test_cleaner.py` (modification at line 113)
**Changes:** Remove the `@pytest.mark.xfail` decorator since the fix will make the test pass

**Current:**
```python
@pytest.mark.xfail(reason="TextCleaner does not currently normalize curly quotes - known gap")
def test_curly_quotes_normalized(self, cleaned_data: List[Dict]):
```

**Fixed:**
```python
def test_curly_quotes_normalized(self, cleaned_data: List[Dict]):
```

---

## Success Criteria

### Automated Verification:

- [ ] Tests pass: `pytest tests/preprocessing/test_cleaner.py -v`
- [ ] Curly quote test specifically passes: `pytest tests/preprocessing/test_cleaner.py::TestCleanerHygieneWithRealData::test_curly_quotes_normalized -v`
- [ ] No regressions in other cleaner tests

### Manual Verification:

- [ ] Run TextCleaner on text with curly quotes and confirm they are normalized:
```python
from src.preprocessing.cleaning import TextCleaner
cleaner = TextCleaner()
text = 'He said "hello" and it's working'
cleaned = cleaner.clean_text(text)
assert '"' not in cleaned and '"' not in cleaned
assert ''' not in cleaned and ''' not in cleaned
```

---

## Implementation Notes

Unicode Reference:
| Character | Name | Unicode | Replacement |
|-----------|------|---------|-------------|
| " | Left Double Quote | U+201C | " (U+0022) |
| " | Right Double Quote | U+201D | " (U+0022) |
| ' | Left Single Quote | U+2018 | ' (U+0027) |
| ' | Right Single Quote | U+2019 | ' (U+0027) |
