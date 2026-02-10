# NLP Validation Report

**Status**: `GENERATED`
**Data Source**: `AAPL_10K_2021_segmented_risks.json`

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `2025-12-15T16:58:44.482882-06:00` |
| **Researcher** | `bethCoderNewbie` |
| **Git Commit** | `1843e0d` (Branch: `main`) |
| **Python** | `3.13.5` |
| **Platform** | `Windows-11-10.0.22631-SP0` |

---

## 1. Executive Summary

This report validates the internal consistency and domain-appropriateness of the NLP feature extraction pipelines.

| Category | Metric | Value | Target | Status |
|----------|--------|-------|--------|--------|
| **Sentiment** | LM Dictionary Hit Rate | 10.19% | > 2% | ✅ PASS |
| **Sentiment** | Zero-Vector Rate | 1.85% | < 50% | ✅ PASS |
| **Sentiment** | Polarity (Neg > Pos) | True | True | ✅ PASS |
| **Readability** | Avg Gunning Fog | 24.6 | 14-22 | ❌ FAIL |
| **Readability** | Metric Correlation | 0.98 | > 0.7 | ✅ PASS |

---

## 2. Sentiment Analysis Details

### Dictionary Effectiveness
* **LM Hit Rate**: `10.19%`
    * *Interpretation*: Percentage of tokens found in the Loughran-McDonald dictionary.
    * *Target*: > 2% (Typical 10-K is 3-5%). A low value suggests tokenization issues.

* **Zero-Vector Rate**: `1.85%` (1 segments)
    * *Interpretation*: Percentage of segments with NO sentiment words.
    * *Target*: < 50%. High values indicate "silent failures" in matching.

### 10-K Domain Profile
* **Negative Ratio**: `0.0454`
* **Positive Ratio**: `0.0054`
* **Uncertainty Ratio**: `0.0326`
* **Uncertainty-Negative Correlation**: `0.63`
    * *Interpretation*: "Risk" words should correlate with "Uncertainty" words (e.g., "may", "could"). A positive correlation (> 0.3) confirms this relationship.

---

## 3. Readability Analysis Details

### Score Plausibility
* **Gunning Fog Index**:
    * Average: `24.6` (Target: 14-22)
    * Min: `17.2` (Target: > 8)
    * Max: `41.4` (Target: < 35)
    * *Interpretation*: 10-K Risk Factors are complex (college grad level). 
        * < 10: Check for splitter splitting on abbreviations (e.g., "U.S.").
        * > 35: Check for splitter missing periods.

### Domain Adjustment
* **Financial Adjustment Delta**: `12.71%`
    * *Interpretation*: Reduction in "complex word" count after excluding common financial terms (e.g., "financial", "company").
    * *Target*: > 0.5%. Ensures we aren't penalizing necessary domain jargon.

### Custom Metrics
* **Obfuscation Score**: `80.0`
    * *Interpretation*: Composite score (0-100) of structural complexity and passive voice.
    * *Target*: 35-80 for Risk Factors.

* **Obfuscation-Complexity Correlation**: `0.73`
    * *Target*: > 0.6. Confirms the custom score tracks with standard complexity proxies.

---

## 4. How to Interpret Failures

| Failure Mode | Likely Cause | Suggested Fix |
|--------------|--------------|---------------|
| **LM Hit Rate < 2%** | Tokenizer splitting words or casing mismatch. | Check `SentimentAnalyzer.tokenize` for casing/punctuation handling. |
| **Zero-Vector Rate > 50%** | Dictionary not loading or matching logic broken. | Verify `LMDictionaryManager` path and `_count_matches` logic. |
| **Positive > Negative** | Wrong file or severe bug. | Ensure analyzing **Risk Factors** (Item 1A), not marketing sections. |
| **Fog Index > 35** | Sentence splitter failing. | Check `Segmenter` logic for handling bullet points or missing whitespace. |
| **Fog Index < 10** | Over-splitting. | Check handling of abbreviations (e.g., "Inc.", "Ltd."). |

