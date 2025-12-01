# Topic Modeling Feature Extraction

This module provides LDA-based topic modeling for SEC risk factor analysis. It discovers latent risk topics from Item 1A sections and quantifies each company's exposure to different types of risk.

## Overview

**Goal:** Automatically discover and quantify company exposure to different risk topics (e.g., "Cybersecurity Risk," "Regulatory Risk," "Supply Chain Risk") from Item 1A sections.

**Method:** Latent Dirichlet Allocation (LDA) topic modeling

**Output:** For each company, a probability distribution over discovered risk topics that can be used as classifier features.

## Installation

Required dependencies (already installed):
```bash
pip install gensim nltk
python -m nltk.downloader stopwords
```

## Usage

### 1. Train LDA Model (One-Time Setup)

First, train an LDA model on a corpus of Item 1A sections:

```python
from src.features.topic_modeling import LDATrainer

# Prepare corpus of Item 1A sections
documents = [
    "Risk Factor 1: We face significant cybersecurity threats...",
    "Risk Factor 2: Supply chain disruptions may affect...",
    # ... more Item 1A texts
]

# Train LDA model
trainer = LDATrainer(num_topics=15, passes=10, iterations=100)
model_info = trainer.train(
    documents=documents,
    save_path="models/lda_item1a",
    compute_coherence=True
)

# Inspect discovered topics
trainer.print_topics(num_words=10)
```

**Output Example:**
```
Discovered Topics (n=15):
================================================================================

Topic 0:
  cybersecurity(0.045), data(0.038), breach(0.032), privacy(0.028), ...

Topic 1:
  regulatory(0.051), compliance(0.044), sec(0.035), regulation(0.031), ...

Topic 2:
  supply(0.048), chain(0.042), disruption(0.036), logistics(0.029), ...

...
```

### 2. Extract Features from New Documents

Once trained, use the model to extract features from new documents:

```python
from src.features.topic_modeling import TopicModelingAnalyzer

# Load pre-trained model
analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

# Extract features from new Item 1A section
item1a_text = "..."  # Item 1A text
features = analyzer.extract_features(item1a_text)

# Access features
print(f"Dominant topic: {features.dominant_topic_id}")
print(f"Dominant probability: {features.dominant_topic_probability}")
print(f"Topic entropy: {features.topic_entropy}")
print(f"Topic probabilities: {features.topic_probabilities}")

# Get feature vector for ML model
topic_vector = features.to_feature_vector(analyzer.num_topics)
# Output: [0.15, 0.08, 0.22, 0.05, ...]  # 15 probabilities
```

### 3. Use as Classifier Features

The topic probability distribution is a powerful feature set for classification:

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Extract features for entire dataset
features_list = []
labels = []

for company_data in dataset:
    item1a_text = company_data['item1a']
    label = company_data['outcome']  # e.g., bankruptcy, fraud, etc.

    # Extract topic features
    features = analyzer.extract_features(item1a_text)
    topic_vector = features.to_feature_vector(analyzer.num_topics)

    features_list.append(topic_vector)
    labels.append(label)

# Create DataFrame
X = pd.DataFrame(features_list, columns=[f"topic_{i}" for i in range(analyzer.num_topics)])
y = pd.Series(labels)

# Train classifier
clf = RandomForestClassifier()
clf.fit(X, y)
```

## Features Produced

The `TopicModelingFeatures` model provides the following features:

| Feature | Type | Description |
|---------|------|-------------|
| `topic_probabilities` | Dict[int, float] | Full probability distribution over topics |
| `dominant_topic_id` | int | ID of most prominent topic |
| `dominant_topic_probability` | float | Probability of dominant topic |
| `topic_entropy` | float | Shannon entropy (topic diversity measure) |
| `num_topics` | int | Total number of topics in model |
| `num_significant_topics` | int | Number of topics above threshold (0.25) |

### Feature Vector

For ML models, use `to_feature_vector()`:
```python
feature_vector = features.to_feature_vector(num_topics=15)
# Returns: [0.25, 0.15, 0.08, 0.12, 0.05, ...]  # Length = num_topics
```

This gives you a dense vector where each element represents the company's exposure to that topic.

## Configuration

Configuration is managed via `configs/features/topic_modeling.yaml`:

```yaml
topic_modeling:
  model:
    num_topics: 15        # Number of latent topics
    passes: 10            # Training passes
    iterations: 100       # Iterations per pass
    alpha: "auto"         # Document-topic density
    eta: "auto"           # Topic-word density

  preprocessing:
    no_below: 2           # Min document frequency
    no_above: 0.7         # Max document frequency fraction
    keep_n: 10000         # Keep top N tokens

  features:
    min_probability: 0.01          # Min topic probability threshold
    dominant_threshold: 0.25       # Min prob for dominant topic
```

Override via environment variables:
```bash
export TOPIC_MODELING_MODEL__NUM_TOPICS=20
export TOPIC_MODELING_FEATURES__MIN_PROBABILITY=0.05
```

## Model Quality Evaluation

### Perplexity
Lower is better. Measures how well the model predicts a held-out test set.
- Typical range: -7.0 to -9.0 (log scale)

### Coherence Score
Higher is better. Measures semantic coherence of topics.
- Typical range: 0.3 to 0.7
- > 0.5 is considered good
- > 0.6 is excellent

```python
model_info = trainer.train(documents, compute_coherence=True)
print(f"Perplexity: {model_info.perplexity}")
print(f"Coherence: {model_info.coherence_score}")
```

## Example: Complete Workflow

```python
from pathlib import Path
from src.features.topic_modeling import LDATrainer, TopicModelingAnalyzer
from src.config import settings

# === STEP 1: Train Model (one-time) ===
# Load corpus
corpus = [...]  # List of Item 1A texts

# Train
trainer = LDATrainer(num_topics=15)
trainer.train(corpus, save_path="models/lda_item1a")

# === STEP 2: Extract Features ===
# Load model
analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

# Extract features
new_item1a = "..."
features = analyzer.extract_features(new_item1a)

# View results
analyzer.print_document_topics(new_item1a, num_words=8)
```

**Output:**
```
Document Topic Breakdown:
================================================================================
Topic 3: cybersecurity, data, breach, privacy, security, attack, systems, protection
  Probability: 0.2841 (28.41%)

Topic 7: regulatory, compliance, regulation, sec, fda, law, requirement, enforcement
  Probability: 0.2156 (21.56%)

Topic 12: supply, chain, disruption, logistics, vendor, inventory, procurement, shipping
  Probability: 0.1523 (15.23%)

Topic Entropy: 2.3456
Dominant Topic: 3 (0.2841)
================================================================================
```

## Advanced Usage

### Assigning Human-Readable Labels

After inspecting topics, assign meaningful labels:

```python
topic_labels = {
    0: "Cybersecurity & Data Privacy",
    1: "Regulatory Compliance",
    2: "Supply Chain & Logistics",
    3: "Market Competition",
    4: "Financial Liquidity",
    # ...
}

# Save labels
import json
with open("models/lda_item1a/topic_labels.json", 'w') as f:
    json.dump(topic_labels, f, indent=2)

# Labels will be automatically loaded with the model
analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")
print(analyzer.get_topic_description(0))
# Output: "Cybersecurity & Data Privacy: cybersecurity, data, breach, ..."
```

### Batch Processing

```python
texts = [...]  # List of documents

# Extract features for all documents
features_list = analyzer.extract_features_batch(texts)

# Convert to DataFrame
import pandas as pd
data = []
for features in features_list:
    data.append({
        'dominant_topic': features.dominant_topic_id,
        'entropy': features.topic_entropy,
        **{f'topic_{i}': prob for i, prob in features.topic_probabilities.items()}
    })

df = pd.DataFrame(data)
```

## Tips for Good Topic Models

1. **Corpus Size**: Aim for 200+ documents for reliable topic discovery. Minimum 50.

2. **Preprocessing**: Financial stopwords are automatically handled. See `constants.FINANCIAL_STOPWORDS`.

3. **Number of Topics**:
   - Start with 10-20 topics
   - Too few: Topics too broad
   - Too many: Topics too specific/noisy
   - Use coherence score to tune

4. **Topic Coherence**: Inspect top words to ensure topics are interpretable. If not, adjust:
   - Increase/decrease `num_topics`
   - Adjust `no_below`/`no_above` filtering
   - Add domain-specific stopwords

5. **Reproducibility**: Always set `random_state=42` for consistent results.

## Files Created

When training, the following files are saved:

```
models/lda_item1a/
├── lda_model.pkl          # Trained LDA model
├── lda_dictionary.pkl     # Gensim Dictionary (vocabulary)
├── topic_labels.json      # Human-readable topic labels (optional)
└── model_info.json        # Model metadata (perplexity, coherence, etc.)
```

## Common Risk Topics

Based on analysis of SEC 10-K filings, common risk topics include:

- Cybersecurity & Data Privacy
- Regulatory & Compliance
- Supply Chain & Logistics
- Market Competition
- Financial Liquidity & Credit
- Intellectual Property
- Legal & Litigation
- Operational Disruption
- Economic Conditions
- Technology & Innovation
- Environmental & Climate
- Geopolitical & Trade
- Human Capital & Talent
- Customer Concentration
- Product Liability

Your LDA model will discover topics specific to your corpus!

## References

- Blei, D. M., Ng, A. Y., & Jordan, M. I. (2003). Latent dirichlet allocation. Journal of machine Learning research, 3(Jan), 993-1022.
- [Gensim LDA Documentation](https://radimrehurek.com/gensim/models/ldamodel.html)
