# Running Scripts - Quick Reference

**IMPORTANT**: Always activate the virtual environment before running any Python scripts!

## Activation

```bash
# Activate virtual environment
source venv/bin/activate

# You should see (venv) in your prompt
# Example: (venv) beth@computer:/home/beth/work/SEC-finetune$
```

## Common Scripts

### Download SEC Filings

```bash
# Make sure venv is active first!
source venv/bin/activate

# Download optimal corpus for topic modeling
python scripts/data_collection/download_sec_filings.py --mode topic-modeling

# Download specific ticker
python scripts/data_collection/download_sec_filings.py --ticker AAPL --years 3

# Download from ticker file
python scripts/data_collection/download_sec_filings.py --ticker-file tickers.txt
```

### Run Preprocessing Pipeline

```bash
source venv/bin/activate

# Single file
python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html

# Batch mode
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
```

### Run Streamlit UI

```bash
source venv/bin/activate

streamlit run src/visualization/app.py
```

## Deactivation

When you're done working:

```bash
deactivate
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'XXX'"

**Cause**: Virtual environment not activated

**Fix**:
```bash
source venv/bin/activate
```

### Check if venv is active

```bash
which python
# Should show: /home/beth/work/SEC-finetune/venv/bin/python

# If it shows /usr/bin/python or /usr/local/bin/python, venv is NOT active!
```
