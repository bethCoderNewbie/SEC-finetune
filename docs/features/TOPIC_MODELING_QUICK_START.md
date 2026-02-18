# Topic Modeling Quick Start Guide

## TL;DR - Optimal Data Requirements

For **best balance of efficiency, latency, and quality**:

```
✅ Corpus Size:        300-500 documents
✅ Document Length:    2,000-3,000 words average
✅ Industries:         8-12 different sectors
✅ Time Range:         3-5 years
✅ Unique Companies:   200-400
✅ Training Time:      6-10 minutes
✅ Inference Latency:  <100ms per document
✅ Expected Coherence: 0.48-0.52
```

Run the scripts to download sec filling in html:

```bash
python scripts/data_collection/download_sec_filings.py --mode topic-modeling
```
## Before You Start: Validate Your Corpus

Run the validation script to check if your data is ready:

```bash
python scripts/data_collection/download_sec_filings.py --mode topic-modeling
python scripts/feature_engineering/validate_topic_modeling_corpus.py
```

This will tell you:
- ✅ What's good
- ⚠️  What needs improvement
- ❌ What's blocking you

## Quick Training Workflow

### Step 1: Load Your Data

```python
from src.features.topic_modeling import LDATrainer
import json
from pathlib import Path

# Load Item 1A sections
documents = []
extracted_dir = Path("data/interim/extracted")

for file in extracted_dir.glob("*_extracted.json"):
    with open(file) as f:
        data = json.load(f)
        if 'sections' in data and 'part1item1a' in data['sections']:
            text = data['sections']['part1item1a']['text']
            documents.append(text)

print(f"Loaded {len(documents)} documents")
```

### Step 2: Train LDA Model

```python
# Train with optimal settings
trainer = LDATrainer(
    num_topics=15,       # Good for most use cases
    passes=10,           # Balance quality/speed
    iterations=100,
    random_state=42,     # Reproducibility
)

model_info = trainer.train(
    documents=documents,
    save_path="models/lda_item1a",
    compute_coherence=True
)

# Check quality
print(f"Coherence: {model_info.coherence_score:.4f}")  # Target: >0.45
print(f"Perplexity: {model_info.perplexity:.4f}")

# Inspect topics
trainer.print_topics(num_words=10)
```

### Step 3: Extract Features

```python
from src.features.topic_modeling import TopicModelingAnalyzer

# Load trained model
analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

# Extract features for a new document
new_item1a = "..."  # Your Item 1A text
features = analyzer.extract_features(new_item1a)

# Use as classifier features
topic_vector = features.to_feature_vector(analyzer.num_topics)
# Result: [0.15, 0.08, 0.22, ...]  # 15 probabilities
```

## Configuration Tuning by Use Case

### Prototype (Fast & Quick)
```python
# Goal: Test feasibility in <5 minutes
corpus_size = 100-150
num_topics = 10
passes = 5
iterations = 50
# Training: ~2 min, Coherence: ~0.40
```

### Production (Balanced)
```python
# Goal: Production-ready quality
corpus_size = 300-500
num_topics = 15
passes = 10
iterations = 100
# Training: ~8 min, Coherence: ~0.50
```

### Research (Maximum Quality)
```python
# Goal: Publishable results
corpus_size = 500-1000
num_topics = 15-20
passes = 15
iterations = 150
# Training: ~15 min, Coherence: >0.55
```

## Data Quality Checklist

Before training, ensure:

- [ ] **At least 200 documents** (300+ preferred)
- [ ] **Documents are 1,000+ words** on average (2,500+ preferred)
- [ ] **5+ different industries** represented (8+ preferred)
- [ ] **No duplicate documents**
- [ ] **HTML tags removed** (use TextCleaner)
- [ ] **Boilerplate removed** (headers, footers, page numbers)
- [ ] **Actually Item 1A sections** (not other parts of 10-K)
- [ ] **Recent data** (within last 5-10 years)

## Common Issues & Solutions

### Issue: Low Coherence (<0.35)

**Causes:**
- Corpus too small (<100 docs)
- Too many topics for corpus size
- Poor text quality

**Solutions:**
- Add more documents
- Reduce `num_topics` to 8-10
- Improve preprocessing (remove HTML, boilerplate)
- Check for duplicates

### Issue: Topics Look Generic/Random

Example bad topic:
```
Topic 3: company, business, may, operations, results, year
```

**Causes:**
- Insufficient stopword filtering
- `NO_ABOVE` too high (includes generic terms)

**Solutions:**
- Add more financial stopwords (already configured)
- Lower `NO_ABOVE` from 0.7 to 0.5-0.6
- Increase `NO_BELOW` from 2 to 3-5

### Issue: All Documents Get Same Topic

**Causes:**
- Lack of diversity (all same industry)
- Too few topics

**Solutions:**
- Diversify corpus across industries
- Increase `num_topics` to 12-15
- Use `alpha='auto'` instead of fixed value

## Expected Performance Benchmarks

| Corpus Size | Training Time | Inference | Coherence | Vocabulary |
|-------------|---------------|-----------|-----------|------------|
| 100 docs    | 2-3 min       | 60ms      | 0.38-0.42 | 2-3K words |
| 200 docs    | 4-6 min       | 70ms      | 0.42-0.46 | 3-4K words |
| 300 docs    | 6-8 min       | 80ms      | 0.46-0.50 | 4-5K words |
| 500 docs    | 10-12 min     | 90ms      | 0.50-0.54 | 5-6K words |
| 1000 docs   | 15-20 min     | 100ms     | 0.52-0.56 | 6-8K words |

*Benchmarks based on: 15 topics, 10 passes, 100 iterations, average document length 2,500 words*

## Recommended Corpus Composition

### Industry Distribution (for 300 documents)
```
Technology:          20% (60 docs)
Healthcare:          15% (45 docs)
Financial Services:  15% (45 docs)
Consumer Goods:      12% (36 docs)
Manufacturing:       10% (30 docs)
Energy:              8%  (24 docs)
Real Estate:         6%  (18 docs)
Other:               14% (42 docs)
```

### Company Size Distribution
```
Large Cap (>$10B):   40% (120 docs)
Mid Cap ($2B-10B):   40% (120 docs)
Small Cap (<$2B):    20% (60 docs)
```

### Temporal Distribution (3-year window)
```
Most recent year:    40% (120 docs)  # Higher weight
Year -1:             35% (105 docs)
Year -2:             25% (75 docs)
```

## Feature Output Example

After training and extracting features, you get:

```python
features = {
    'topic_probabilities': {
        0: 0.05,   # Cybersecurity Risk
        1: 0.12,   # Regulatory Risk
        2: 0.08,   # Market Competition
        3: 0.28,   # Supply Chain Risk (dominant)
        4: 0.15,   # Financial Risk
        5: 0.07,   # IP/Litigation Risk
        # ... (15 topics total)
    },
    'dominant_topic_id': 3,
    'dominant_topic_probability': 0.28,
    'topic_entropy': 2.34,
    'num_significant_topics': 4,
}
```

Use this as input to your classifier:
```python
X_topics = features.to_feature_vector(15)
# [0.05, 0.12, 0.08, 0.28, 0.15, 0.07, ...]
```

## Next Steps

1. **Validate your corpus:**
   ```bash
   python scripts/feature_engineering/validate_topic_modeling_corpus.py
   ```

2. **Run the demo:**
   ```bash
   python scripts/feature_engineering/topic_modeling_demo.py
   ```

3. **Read detailed docs:**
   - Full guide: `docs/topic_modeling_data_requirements.md`
   - Module docs: `src/features/topic_modeling/README.md`

4. **Train your model and iterate:**
   - Start with prototype settings (100-150 docs, 10 topics)
   - Check coherence and inspect topics
   - Scale up to production (300+ docs, 15 topics)

## Key Takeaways

✅ **300-500 documents** is the sweet spot for production

✅ **15 topics** works well for most SEC risk factor analysis

✅ **3-5 years** of data balances recency and diversity

✅ **8-12 industries** ensures good generalization

✅ **Validate first** using the validation script

✅ **Expect 0.48-0.52 coherence** with good data

✅ **<100ms inference** is achievable with proper configuration

Good luck! 🚀
