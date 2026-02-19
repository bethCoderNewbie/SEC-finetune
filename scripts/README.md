# Scripts Directory - ML Lifecycle Organization

This directory contains all scripts organized by the machine learning lifecycle stages.

## Directory Structure

```
scripts/
├── 01_data_collection/       # Download and acquire SEC filings
├── 02_data_preprocessing/    # Parse, extract, clean, segment filings
├── 03_eda/                   # Exploratory data analysis
├── 04_feature_engineering/   # Extract features and embeddings
├── 05_data_splitting/        # Create train/val/test splits
├── 06_training/              # Train and fine-tune models
├── 07_evaluation/            # Evaluate model performance
├── 08_inference/             # Run predictions on new data
├── 09_deployment/            # Deploy models to production
├── 10_monitoring/            # Monitor model performance
└── utils/                    # Utility scripts (setup, debugging, testing)
```

## ML Lifecycle Stages

### Stage 1: Data Collection
**Directory**: `01_data_collection/`

Scripts for downloading SEC filings from EDGAR.

**Scripts:**
- `download_sec_filings.py` - Download filings for specified tickers

**Usage:**
```bash
python scripts/data_collection/download_sec_filings.py --ticker AAPL
python scripts/data_collection/download_sec_filings.py --ticker-file tickers.txt
```

### Stage 2: Data Preprocessing
**Directory**: `02_data_preprocessing/`

Parse, extract, clean, and segment SEC filings.

**Scripts:**
- `batch_parse.py` - Batch parse multiple HTML filings
- `run_preprocessing_pipeline.py` - Run complete preprocessing pipeline

**Usage:**
```bash
# Batch parsing
python scripts/data_preprocessing/batch_parse.py

# Full pipeline
python scripts/data_preprocessing/run_preprocessing_pipeline.py
```

### Stage 3: Exploratory Data Analysis
**Directory**: `03_eda/`

Analyze data distributions, patterns, and characteristics.

**Scripts:**
- `exploratory_analysis.py` - Comprehensive EDA on parsed filings

**Usage:**
```bash
python scripts/eda/exploratory_analysis.py
```

### Stage 4: Feature Engineering
**Directory**: `04_feature_engineering/`

Extract features and create embeddings for ML models.

**Scripts:**
- `extract_features.py` - Extract text features and embeddings

**Usage:**
```bash
python scripts/feature_engineering/extract_features.py
python scripts/feature_engineering/extract_features.py --embedding-model sentence-transformers
```

### Stage 5: Data Splitting
**Directory**: `05_data_splitting/`

Create train/validation/test splits.

**Scripts:**
- `create_train_test_split.py` - Split data with stratification or temporal logic

**Usage:**
```bash
# Stratified split
python scripts/data_splitting/create_train_test_split.py --test-size 0.2 --val-size 0.1

# Temporal split
python scripts/data_splitting/create_train_test_split.py --split-type temporal \
    --temporal-val-year 2021 --temporal-test-year 2022
```

### Stage 6: Training
**Directory**: `06_training/`

Train and fine-tune language models.

**Scripts:**
- `train_model.py` - Train LLM on SEC risk factor data

**Usage:**
```bash
python scripts/training/train_model.py
python scripts/training/train_model.py --model-name meta-llama/Llama-2-7b-hf
python scripts/training/train_model.py --resume models/checkpoint-1000
```

### Stage 7: Evaluation
**Directory**: `07_evaluation/`

Evaluate trained model performance.

**Scripts:**
- `evaluate_model.py` - Calculate metrics and generate evaluation reports

**Usage:**
```bash
python scripts/evaluation/evaluate_model.py
python scripts/evaluation/evaluate_model.py --model models/sec-risk-model
```

### Stage 8: Inference
**Directory**: `08_inference/`

Run predictions on new SEC filings.

**Scripts:**
- `predict.py` - Single or batch inference on new filings

**Usage:**
```bash
# Single file
python scripts/inference/predict.py --input data/raw/AAPL_10K.html

# Batch inference
python scripts/inference/predict.py --batch --input-dir data/raw/
```

### Stage 9: Deployment
**Directory**: `09_deployment/`

Deploy models to production environments.

**Scripts:**
- (Templates to be implemented based on deployment strategy)

### Stage 10: Monitoring
**Directory**: `10_monitoring/`

Monitor model performance in production.

**Scripts:**
- (Templates to be implemented for production monitoring)

### Utilities
**Directory**: `utils/`

Development, debugging, and testing utilities.

**Subdirectories:**
- `debugging/` - Diagnostic and debugging tools
- `inspection/` - Data inspection tools
- `testing/` - Testing utilities

**Scripts:**
- `check_installation.py` - Validate environment setup
- `setup_nlp_models.py` - Download required NLP models
- `doc_gen.py` - Generate structured docs (PRD, RFC, ADR, User Story) via Claude CLI
- `debugging/diagnose_extraction.py` - Diagnose extraction issues
- `debugging/debug_node_structure.py` - Debug tree structure
- `inspection/inspect_parsed.py` - Inspect parsed filings
- `testing/test_extractor_fix.py` - Test extraction fixes

**Usage (`doc_gen.py`):**
```bash
# Preview assembled prompt without calling Claude
python scripts/utils/doc_gen.py story "Zero-segment filings must hard-FAIL QA" --dry-run

# Print generated document to stdout (redirect to file manually)
python scripts/utils/doc_gen.py rfc "How to integrate classification into batch pipeline"

# Auto-save to the correct docs/ path with the next sequential ID
python scripts/utils/doc_gen.py prd  "Automated daily ingestion from EDGAR" --save
python scripts/utils/doc_gen.py rfc  "Classification integration design" --save
python scripts/utils/doc_gen.py adr  "Use JSONL as training output format" --save --slug jsonl_training_output
python scripts/utils/doc_gen.py story "Pipeline operator can pause a running batch" --save
```

Skill templates live in `.claude/skills/`. The script auto-detects the next sequential ID
by scanning existing files in the target `docs/` directory.

See `utils/README.md` for detailed documentation.

## Naming Conventions

### Directory Names
- Use numbered prefixes (01_, 02_, etc.) to maintain logical order
- Use descriptive names that clearly indicate the ML stage
- Use snake_case for directory names

### Script Names
- Use descriptive, action-oriented names (e.g., `download_`, `train_`, `evaluate_`)
- Use snake_case for file names
- Include comprehensive docstrings with usage examples

### Script Structure
Each script should include:
1. Module docstring with purpose, stage, inputs/outputs, and usage
2. Argument parser with helpful descriptions
3. Main function that orchestrates the workflow
4. Clear progress output and logging

## Running Scripts

### General Pattern
```bash
# Navigate to project root
cd "C:\Users\bichn\MSBA\SEC finetune"

# Run script with appropriate arguments
python scripts/<stage>/<script_name>.py [OPTIONS]
```

### Common Options
Most scripts support:
- `--help` - Show help message
- `--input-dir` - Input directory path
- `--output-dir` - Output directory path
- Various stage-specific options

### Environment
Ensure you have:
1. Activated the virtual environment
2. Installed all dependencies (`pip install -e .`)
3. Set up required environment variables (see `.env.example`)

## Development Guidelines

### Adding New Scripts
1. Place script in the appropriate lifecycle stage directory
2. Follow the template structure
3. Include comprehensive docstrings
4. Add usage examples
5. Update this README

### Best Practices
- Keep scripts focused on single responsibilities
- Use `src/` modules for reusable logic
- Save outputs to appropriate `data/` subdirectories
- Include progress indicators and logging
- Handle errors gracefully
- Make scripts idempotent when possible

### Configuration
- Use `src/config.py` for path configuration
- Use `configs/` directory for Hydra configs
- Use `.env` for secrets and credentials

## Integration with Pipeline

These scripts represent discrete stages in the ML pipeline:

```
Data Collection → Preprocessing → EDA → Feature Engineering →
Data Splitting → Training → Evaluation → Inference → Deployment → Monitoring
```

For full pipeline automation, see:
- `src/main.py` - Main pipeline orchestrator
- Makefile - Convenience commands
- `.github/workflows/` - CI/CD automation

## Troubleshooting

### Common Issues
1. **Import errors**: Ensure you're running from project root
2. **Path errors**: Check that data directories exist
3. **Dependencies**: Run `python scripts/utils/check_installation.py`

### Getting Help
- Check individual script help: `python scripts/<stage>/<script>.py --help`
- See documentation in `docs/`
- Review `utils/debugging/` scripts for diagnostic tools

## Future Enhancements

Planned additions:
- Deployment automation scripts
- Model monitoring dashboards
- Data versioning with DVC
- Experiment tracking with MLflow/Weights & Biases
- Hyperparameter tuning automation
