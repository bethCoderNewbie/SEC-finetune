# Features

Documentation for `src/features/`: sentiment analysis, readability metrics, topic modeling, and the Loughran-McDonald dictionary.

## Start Here

| File | Purpose |
|------|---------|
| [FEATURE_ENGINEERING_GUIDE.md](FEATURE_ENGINEERING_GUIDE.md) | Overview of all feature types, schemas, and how they compose |

## Topic Modeling

| File | Purpose |
|------|---------|
| [TOPIC_MODELING_QUICK_START.md](TOPIC_MODELING_QUICK_START.md) | **Start here** for LDA training and inference |
| [TOPIC_MODELING_REQ.md](TOPIC_MODELING_REQ.md) | Data volume and format requirements for training |
| [2025-11-17_LDA_TRAINING_NOTES.md](2025-11-17_LDA_TRAINING_NOTES.md) | Lab notes from initial LDA training runs |

## Feature Modules

```
src/features/
├── sentiment.py                  → Loughran-McDonald sentiment scoring
├── readability/analyzer.py       → Readability metrics (Flesch, Fog, etc.)
├── topic_modeling/lda_trainer.py → LDA model training
├── topic_modeling/analyzer.py    → Topic inference on new documents
└── dictionaries/lm_dictionary.py → LM dictionary loader
```
