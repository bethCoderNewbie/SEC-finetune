# Data Requirements for LDA Topic Modeling on Item 1A Sections

This guide provides detailed requirements for building an optimal corpus of Item 1A sections to train high-quality LDA models with efficient performance.

## Executive Summary

| Metric | Minimum | Recommended | Optimal | Diminishing Returns |
|--------|---------|-------------|---------|-------------------|
| **Corpus Size** | 50 documents | 200-300 documents | 500-1,000 documents | >2,000 documents |
| **Document Length** | 500 words | 1,500-3,000 words | 2,000-5,000 words | >10,000 words |
| **Unique Companies** | 40 | 150-250 | 400-800 | >1,500 |
| **Time Range** | 1 year | 3-5 years | 5-10 years | >15 years |
| **Industries** | 3-5 sectors | 8-12 sectors | All major sectors | N/A |
| **Vocabulary Size** | 1,000 words | 3,000-5,000 words | 5,000-8,000 words | >15,000 words |

---

## 1. Corpus Size (Number of Documents)

### Minimum Requirements
- **Absolute minimum**: 50 documents
  - LDA will run but topics may be unstable
  - High variance in topic quality
  - Risk of overfitting

- **Practical minimum**: 100-150 documents
  - Topics start to stabilize
  - Acceptable for initial prototyping
  - Still limited generalization

### Recommended Range: 200-300 Documents

**Why this range is optimal:**

1. **Statistical Reliability**
   - Sufficient samples for stable topic discovery
   - Law of large numbers begins to apply
   - Topics become reproducible across runs

2. **Computational Efficiency**
   - Training time: 2-5 minutes (with default settings)
   - Inference latency: <100ms per document
   - Memory footprint: <500MB

3. **Quality vs. Cost Trade-off**
   - Diminishing returns beyond 500 documents for most use cases
   - Coherence scores plateau around 300-400 documents

### Optimal Range: 500-1,000 Documents

**Benefits:**
- Maximum topic coherence and stability
- Better rare topic discovery
- Reduced sensitivity to hyperparameters
- More robust to corpus composition changes

**Training Performance:**
- Training time: 5-15 minutes
- Inference: Still <100ms per document
- Memory: 1-2GB during training

### When to Use More (>1,000 Documents)

**Scenarios:**
- Building a general-purpose risk topic model across all industries
- Need to discover very fine-grained risk subtypes
- Building a production model that will be used for years

**Costs:**
- Training time: 15-60 minutes
- Marginal quality improvement (<5% coherence gain)
- Increased vocabulary size (harder to interpret)

---

## 2. Document Quality & Characteristics

### Length Requirements

**Minimum Document Length: 500 words**
- Below this, documents lack enough context for topic discovery
- LDA struggles with very short texts

**Optimal Length: 1,500-5,000 words**
- Typical Item 1A length: 2,000-8,000 words
- Sweet spot: 2,500-3,500 words
- Provides rich context without overwhelming signal

**Handling Very Long Documents (>10,000 words)**

Option 1: **Chunk into subsections** (Recommended)
```python
def chunk_long_item1a(text: str, max_words: int = 3000) -> List[str]:
    """Split long Item 1A into coherent chunks."""
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        words = sentence.split()
        if current_length + len(words) > max_words:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = len(words)
        else:
            current_chunk.append(sentence)
            current_length += len(words)

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks
```

Option 2: **Sample representative sections**
- Extract first 3,000 words
- May miss topics discussed later

### Text Quality

**Required Preprocessing:**
1. ✅ HTML tags removed
2. ✅ Boilerplate text removed (headers, footers, page numbers)
3. ✅ Table of contents removed
4. ✅ Excessive whitespace normalized
5. ✅ OCR errors corrected (if from scanned PDFs)

**Text Quality Checklist:**
```python
def validate_item1a_quality(text: str) -> Dict[str, bool]:
    """Check if Item 1A meets quality requirements."""
    word_count = len(text.split())

    checks = {
        'sufficient_length': word_count >= 500,
        'not_too_long': word_count <= 15000,
        'has_risk_content': any(word in text.lower() for word in
            ['risk', 'could', 'may', 'uncertain']),
        'not_mostly_numbers': sum(c.isdigit() for c in text) / len(text) < 0.1,
        'not_mostly_uppercase': sum(c.isupper() for c in text if c.isalpha()) /
            sum(c.isalpha() for c in text) < 0.3,
        'has_sentences': '.' in text and len(text.split('.')) > 10,
    }

    return checks
```

---

## 3. Corpus Diversity

### Industry Coverage

**Why diversity matters:**
- Different industries have different risk profiles
- Cybersecurity risks for tech vs. supply chain for manufacturing
- Increases model's generalization ability

**Minimum**: 3-5 major industry sectors
- e.g., Technology, Healthcare, Finance, Manufacturing, Retail

**Recommended**: 8-12 sectors
- Covers most major risk types
- Balances specificity and generality

**Optimal**: Proportional to market composition
```python
# Example target distribution
industry_targets = {
    'Technology': 0.20,
    'Healthcare': 0.15,
    'Financial Services': 0.15,
    'Consumer Goods': 0.12,
    'Manufacturing': 0.10,
    'Energy': 0.08,
    'Real Estate': 0.06,
    'Telecommunications': 0.05,
    'Utilities': 0.04,
    'Other': 0.05,
}
```

### Company Size Diversity

Include mix of:
- **Large cap** (>$10B): Comprehensive risk disclosures
- **Mid cap** ($2B-$10B): Balanced disclosures
- **Small cap** (<$2B): May have emerging/unique risks

**Recommended ratio**: 40% large, 40% mid, 20% small

### Temporal Coverage

**Minimum**: Single year (e.g., all 2023 10-Ks)
- Simplest to collect
- May miss evolving risk topics
- Captures current risk landscape

**Recommended**: 3-5 year rolling window
- Captures risk evolution (e.g., COVID-19, cybersecurity trends)
- Balances stability and recency
- Example: 2019-2023 filings

**Optimal**: 5-10 year window with recency weighting
```python
def get_document_weight(filing_year: int, current_year: int = 2024) -> float:
    """Weight recent documents more heavily."""
    age = current_year - filing_year
    if age <= 2:
        return 2.0  # Double weight for very recent
    elif age <= 5:
        return 1.0  # Normal weight
    else:
        return 0.5  # Half weight for older documents
```

**Avoid**: >15 year windows
- Old risk factors become less relevant
- Regulatory changes (e.g., Cybersecurity now required, wasn't in 2008)
- Increases noise

---

## 4. Vocabulary & Preprocessing

### Target Vocabulary Size

**After Preprocessing:**

| Vocabulary Size | Impact | Recommendation |
|----------------|--------|----------------|
| <1,000 words | Topics too broad, low quality | Insufficient |
| 1,000-3,000 words | Good for simple topic models | Minimum viable |
| 3,000-5,000 words | Optimal balance | **Recommended** |
| 5,000-8,000 words | High quality, more specific topics | Advanced use |
| >10,000 words | Diminishing returns, slower training | Avoid |

### Filtering Strategy

**Configure in `constants.py`:**
```python
# Remove very rare words
NO_BELOW = 2  # Word must appear in at least 2 documents
              # Too low (1): Includes typos, OCR errors
              # Too high (5): Loses rare but meaningful terms

# Remove very common words
NO_ABOVE = 0.7  # Word can appear in max 70% of documents
                # Too low (0.5): Removes important risk terms
                # Too high (0.9): Includes stopwords like "company"

# Keep only top N most frequent
KEEP_N = 10000  # After NO_BELOW/NO_ABOVE filtering
```

**Optimal Settings by Corpus Size:**

| Corpus Size | NO_BELOW | NO_ABOVE | KEEP_N |
|-------------|----------|----------|--------|
| 50-100 docs | 1 | 0.8 | 5,000 |
| 100-300 docs | 2 | 0.7 | 8,000 |
| 300-500 docs | 2-3 | 0.6-0.7 | 10,000 |
| 500-1,000 docs | 3-5 | 0.5-0.6 | 12,000 |
| >1,000 docs | 5 | 0.5 | 15,000 |

### Financial Stopwords

Already included in the module (see `constants.FINANCIAL_STOPWORDS`), but customize if needed:

```python
# Add domain-specific stopwords for your use case
CUSTOM_STOPWORDS = [
    # Generic risk disclosure language
    "may", "could", "would", "might", "risk", "factor",

    # Company-specific (if training on single company over time)
    "acme", "corporation",

    # Regulatory boilerplate
    "sec", "pursuant", "thereof",
]
```

---

## 5. Data Collection Strategy

### Recommended Approach: Stratified Sampling

**Step 1: Define Strata**
```python
strata = {
    'industry': ['Technology', 'Healthcare', 'Finance', ...],
    'market_cap': ['Large', 'Mid', 'Small'],
    'filing_year': [2019, 2020, 2021, 2022, 2023],
}
```

**Step 2: Sample Within Strata**
```python
def stratified_sample(
    universe: pd.DataFrame,
    target_size: int = 300,
    stratify_cols: List[str] = ['industry', 'market_cap']
) -> pd.DataFrame:
    """
    Sample documents to ensure diversity.

    Args:
        universe: Full dataset of available Item 1A sections
        target_size: Desired corpus size
        stratify_cols: Columns to stratify by

    Returns:
        Balanced sample
    """
    from sklearn.model_selection import train_test_split

    # Ensure minimum representation per stratum
    min_per_stratum = max(2, target_size // 50)

    # Stratified sampling
    sample = universe.groupby(stratify_cols, group_keys=False).apply(
        lambda x: x.sample(min(len(x), min_per_stratum))
    )

    # If under target, randomly sample remainder
    if len(sample) < target_size:
        remaining = universe[~universe.index.isin(sample.index)]
        additional = remaining.sample(target_size - len(sample))
        sample = pd.concat([sample, additional])

    return sample.sample(frac=1)  # Shuffle
```

### Data Source Recommendations

**Option 1: SEC EDGAR (Recommended)**
- Most authoritative source
- Free and complete
- Standardized format

**Option 2: Commercial Providers**
- S&P Capital IQ, Bloomberg, FactSet
- Pre-cleaned, structured data
- Expensive but time-saving

**Option 3: Existing Research Datasets**
- WRDS (Wharton Research Data Services)
- Pre-validated Item 1A extractions
- Great for academic use

---

## 6. Balancing Efficiency, Latency, and Quality

### Training Efficiency

**Fast Training (<5 minutes):**
```python
trainer = LDATrainer(
    num_topics=10,        # Fewer topics = faster
    passes=5,             # Fewer passes = faster (but lower quality)
    iterations=50,        # Fewer iterations = faster
    alpha='symmetric',    # Faster than 'auto'
    eta='symmetric',
)

# Corpus: 200-300 documents, 2,000-3,000 words each
# Training time: ~2-4 minutes
# Quality: Good for prototyping
```

**Balanced (5-10 minutes):**
```python
trainer = LDATrainer(
    num_topics=15,        # Standard
    passes=10,            # Good convergence
    iterations=100,
    alpha='auto',         # Learn from data
    eta='auto',
)

# Corpus: 300-500 documents
# Training time: ~6-8 minutes
# Quality: High, suitable for production
```

**High Quality (10-30 minutes):**
```python
trainer = LDATrainer(
    num_topics=20,        # More nuanced topics
    passes=20,            # Excellent convergence
    iterations=200,
    alpha='auto',
    eta='auto',
)

# Corpus: 500-1,000 documents
# Training time: ~15-25 minutes
# Quality: Maximum, for final production model
```

### Inference Latency

**Factors Affecting Latency:**

1. **Vocabulary Size** (most important)
   - 3,000 words: ~50ms per document
   - 5,000 words: ~80ms per document
   - 10,000 words: ~150ms per document

2. **Number of Topics**
   - 10 topics: ~60ms
   - 15 topics: ~80ms
   - 20 topics: ~100ms
   - 30 topics: ~150ms

3. **Document Length**
   - 1,000 words: ~50ms
   - 3,000 words: ~80ms
   - 5,000 words: ~120ms

**Optimization for Low Latency (<100ms):**
```python
# Configuration
NUM_TOPICS = 15          # Good balance
VOCABULARY_SIZE = 5000   # After filtering
MAX_DOCUMENT_LENGTH = 3000  # Truncate if needed

# Preprocessing
NO_BELOW = 3            # Removes rare words
NO_ABOVE = 0.6          # Removes common words
KEEP_N = 5000           # Limit vocabulary

# Expected latency: 60-80ms per document
```

### Quality Metrics

**Measuring Topic Quality:**

1. **Coherence Score** (primary metric)
   - Bad: <0.35
   - Acceptable: 0.35-0.45
   - Good: 0.45-0.55
   - Excellent: >0.55

2. **Perplexity** (secondary metric)
   - Lower is better
   - Useful for comparing models on same corpus
   - Don't optimize perplexity alone (can lead to poor topics)

3. **Human Interpretability** (qualitative)
   - Can you name each topic?
   - Are top words semantically related?
   - Do topics align with known risk categories?

**Example Quality Check:**
```python
def evaluate_topic_quality(trainer: LDATrainer) -> Dict[str, float]:
    """
    Comprehensive quality evaluation.
    """
    # Automatic metrics
    coherence = trainer.model_info.coherence_score
    perplexity = trainer.model_info.perplexity

    # Topic diversity (how distinct are topics?)
    diversity = calculate_topic_diversity(trainer.lda_model)

    # Print topics for manual inspection
    trainer.print_topics(num_words=10)

    return {
        'coherence': coherence,
        'perplexity': perplexity,
        'diversity': diversity,
        'quality_score': coherence * diversity,  # Combined metric
    }
```

---

## 7. Practical Recommendations by Use Case

### Use Case 1: Quick Prototype (1-2 hours)

**Goal**: Prove concept, explore topics

**Data Requirements:**
- Corpus size: 100-150 documents
- Industries: 5-8 major sectors
- Time range: Latest year only
- Company diversity: Don't worry too much

**Configuration:**
```python
trainer = LDATrainer(
    num_topics=10,
    passes=5,
    iterations=50,
)
```

**Expected Quality:**
- Coherence: 0.40-0.45
- Inference: <80ms
- Training: <3 minutes

---

### Use Case 2: Research Project (1 day)

**Goal**: Publishable results, reproducible

**Data Requirements:**
- Corpus size: 300-500 documents
- Industries: All major sectors, balanced
- Time range: 3-5 years
- Stratified sampling by industry and size

**Configuration:**
```python
trainer = LDATrainer(
    num_topics=15,
    passes=10,
    iterations=100,
    random_state=42,  # Reproducibility
)
```

**Expected Quality:**
- Coherence: 0.48-0.55
- Inference: <100ms
- Training: ~8 minutes

---

### Use Case 3: Production Classifier (1 week)

**Goal**: Maximum quality, will be used for years

**Data Requirements:**
- Corpus size: 500-1,000 documents
- Industries: Proportional to market
- Time range: 5-10 years with recency weighting
- Quality validation on each document

**Configuration:**
```python
trainer = LDATrainer(
    num_topics=20,
    passes=15,
    iterations=150,
    random_state=42,
)

# Train multiple models, pick best by coherence
```

**Expected Quality:**
- Coherence: >0.55
- Inference: ~120ms
- Training: ~15 minutes
- Validation: Manual topic labeling

---

## 8. Red Flags: When Your Corpus Has Issues

### Problem: Low Coherence (<0.35)

**Likely Causes:**
1. Corpus too small (<100 documents)
2. Documents too short (<500 words)
3. Too many topics for corpus size
4. Poor text quality (OCR errors, HTML artifacts)

**Solutions:**
- Increase corpus size
- Reduce num_topics
- Improve preprocessing
- Check for duplicate documents

### Problem: Topics Look Random/Uninterpretable

**Example Bad Topic:**
```
Topic 5: company, business, may, year, market, operations, financial, results, period, risk
```
(All generic terms, no semantic coherence)

**Likely Causes:**
1. Insufficient stopword filtering
2. Vocabulary too large (>15,000 words)
3. NO_ABOVE too high (includes generic terms)

**Solutions:**
- Add more financial stopwords
- Reduce KEEP_N
- Lower NO_ABOVE to 0.5-0.6
- Increase NO_BELOW to 3-5

### Problem: All Documents Assigned Same Topic

**Likely Causes:**
1. Corpus lacks diversity (e.g., all same industry)
2. Too few topics (e.g., num_topics=3)
3. Alpha/eta hyperparameters wrong

**Solutions:**
- Diversify corpus across industries
- Increase num_topics to 10-15
- Use alpha='auto' and eta='auto'

---

## 9. Checklist: Is My Corpus Ready?

Use this checklist before training:

```python
def validate_corpus_readiness(documents: List[str]) -> Dict[str, Any]:
    """
    Validate corpus meets requirements.
    """
    import numpy as np

    # Basic stats
    num_docs = len(documents)
    doc_lengths = [len(doc.split()) for doc in documents]

    # Vocabulary
    all_words = set()
    for doc in documents:
        all_words.update(doc.lower().split())
    vocab_size = len(all_words)

    checks = {
        '✅ Sufficient documents (>=200)': num_docs >= 200,
        '✅ Not too many documents (<=2000)': num_docs <= 2000,
        '✅ Documents long enough (avg >1000 words)': np.mean(doc_lengths) > 1000,
        '✅ Documents not too long (avg <8000 words)': np.mean(doc_lengths) < 8000,
        '✅ Reasonable vocabulary (3k-10k words)': 3000 <= vocab_size <= 10000,
        '✅ Documents have variety (length std >500)': np.std(doc_lengths) > 500,
    }

    stats = {
        'num_documents': num_docs,
        'avg_document_length': np.mean(doc_lengths),
        'vocabulary_size': vocab_size,
    }

    return {'checks': checks, 'stats': stats}

# Usage
results = validate_corpus_readiness(your_item1a_texts)
for check, passed in results['checks'].items():
    print(f"{check}: {'PASS' if passed else 'FAIL'}")
```

---

## 10. Quick Reference Table

| Goal | Corpus Size | Num Topics | Training Time | Coherence | Use When |
|------|-------------|------------|---------------|-----------|----------|
| **Quick Test** | 50-100 | 5-10 | 1-2 min | 0.30-0.40 | Exploring feasibility |
| **Prototype** | 150-200 | 10-12 | 3-5 min | 0.40-0.45 | Initial development |
| **Production (Fast)** | 200-300 | 12-15 | 5-8 min | 0.45-0.50 | Time-sensitive apps |
| **Production (Quality)** | 300-500 | 15-20 | 8-15 min | 0.50-0.55 | Standard production |
| **Research Grade** | 500-1,000 | 15-25 | 15-25 min | 0.55+ | Publications, long-term use |

---

## Summary: Optimal Configuration

For **most use cases**, this is the sweet spot:

```python
# Corpus Characteristics
CORPUS_SIZE = 300  # documents
AVG_DOCUMENT_LENGTH = 2500  # words
TIME_RANGE = "3-5 years"
INDUSTRIES = "8-12 sectors, balanced"
COMPANIES = "250 unique companies"

# Model Configuration
trainer = LDATrainer(
    num_topics=15,
    passes=10,
    iterations=100,
    random_state=42,
    alpha='auto',
    eta='auto',
)

# Expected Results
TRAINING_TIME = "6-8 minutes"
INFERENCE_LATENCY = "80-100ms per document"
COHERENCE_SCORE = "0.48-0.52"
VOCABULARY_SIZE = "4,000-6,000 words"
```

This configuration provides:
- ✅ High-quality, interpretable topics
- ✅ Fast enough for production (sub-100ms inference)
- ✅ Reasonable training time (can retrain monthly)
- ✅ Robust to corpus variations
- ✅ Good generalization to new documents

---

## Additional Resources

- See `src/features/topic_modeling/README.md` for usage examples
- See `scripts/04_feature_engineering/topic_modeling_demo.py` for complete workflow
- Gensim LDA Tuning: https://radimrehurek.com/gensim/auto_examples/tutorials/run_lda.html
- Topic Coherence Metrics: https://radimrehurek.com/gensim/models/coherencemodel.html
