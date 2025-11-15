# 🚀​ MLOps Code Guidance: The sec-filing-analyzer​

​This document outlines the official code and project structure for the sec-filing-analyzer.​ ​Adhering to this guidance is essential for maintaining a project that is​​scalable,​ **​reproducible, maintainable, and production-ready​.​**

## ​1. Core Principles​

​Our architecture is built on a few key MLOps principles:​

* Separation of Concerns (SoC):​​Every part of the project​​has a specific, well-defined​ ​job.​
Training vs. Inference:​​Code for​​creating​​a model​​(llm_finetuning/) is separate from​ ​code for​​using​​a model (src/analysis/).​
​​Code vs. Config:​​Logic (src/) is separate from parameters​​and settings (configs/).​ ​This allows us to change experiments or service endpoints without changing the​ ​code.​
​Data I/O vs. Business Logic:​​ How we connect to a database​ ​(src/storage/db_clients.py) is separate from​​ what ​​we do with that database​ ​(src/storage/mongo_repo.py).​
* ​Version Everything:​​We version not just our code (Git),​​but also our data (DVC), models​ ​(Git LFS or DVC), and database schemas (alembic).​
​* Reproducibility:​​Our Dockerfile, docker-compose.yml,​​and pyproject.toml ensure that ​any developer (or CI/CD runner) can create an identical environment and reproduce our​ ​results.​
* Production First:​​src/ is built as an installable​​Python package. This enables robust​ ​testing, reusability, and deployment as a service (e.g., API).​

-----

## ​2. Directory & File Breakdown​

### 📂​ src/: The Production Code Package​

​This is the heart of the application. It is structured as an installable Python package.​
​●​ ​src/acquisition/​: Responsible for​​getting​​data (e.g.,​​edgar_client.py).​
​●​ ​src/preprocessing/​: The "refinery." Responsible for​​cleaning, parsing, and segmenting​ ​raw data (parser.py, extractor.py, cleaning.py, segmenter.py).​
​●​ ​src/analysis/​: The "brains." Responsible for running​​inference with the​​trained​​model​ ​(inference.py) and deriving value (insights.py).​​This​​code does not train models.​
​●​ ​src/visualization/​: The "face." Responsible for serving ​​results, whether as an API (api.py)​ ​or a dashboard (app.py).​
​●​ ​src/storage/​: The database "gatekeeper." This is a​​critical component for abstracting all​ ​data I/O.​
​○​ ​schemas/​: The​​single source of truth​​for our data.​​mongo_schemas.py (Pydantic)​ ​defines the shape of our "filing index" documents, while postgres_schemas.py​ ​(SQLAlchemy) defines our "analysis results" tables.​
​○​ ​db_clients.py​: Handles the​​how​​(e.g., creating the​​connection pool for Postgres,​ ​getting the Mongo client). It gets credentials from config.py.​
​○​ ​mongo_repo.py / postgres_repo.py​: Define the​​what​.​​These files import the​ ​schemas and clients to provide clean, high-level functions for the rest of the app​ ​(e.g., postgres_repo.insert_risk_factor()).​

### 🔬​ llm_finetuning/​
​This directory holds all scripts, configs, and utilities related to​​training or fine-tuning​​ your​ ​model. It is intentionally separate from src/ because training is an ​​experimentation​​ and​ _​engineering​​task, while inference is a​​production​​task.​_
​●​ ​synthesize_dataset.py: Uses production data (from src.storage.postgres_repo) to build a​ ​new training dataset.​
​●​ ​train.py: The main script to run the fine-tuning job.​
​●​ ​evaluate.py: Script to evaluate a trained model checkpoint.​

-----

### 🔧​ configs/​

​This directory separates all configuration from code.​

​●​ ​data/ & model/​: Holds Hydra-compatible YAMLs for defining​​datasets and model​ ​hyperparameters (e.g., learning rate, model name). This allows you to run experiments​ ​like: python train.py model=llm_base data=finetune_dataset​
​●​ ​core/services.yaml​: Defines the​​infrastructure​​configuration:​​database URLs, S3 bucket​ ​names, API endpoints. This file defines the ​​shape ​​of configuration your app expects.​​ Do​ **​not store secrets here.​​ Secrets are loaded from environment​​variables (see​ ​.env.example).​

### 🗃️​ data/ & models/​

​These directories are​​placeholders​​for versioned artifacts.​

​●​ ​Git vs. DVC/LFS:​​Git is for code. Large files (data,​​models) are tracked by DVC (metadata​ ​in .dvc/) or Git LFS (pointers in .gitattributes).​
​●​ ​Storage:​​The​​actual​​files live in remote storage (like​​S3, MinIO, or a database).​
​●​ ​data/​: Contains small, sample files for testing (data/raw).​​The data/processed folder​ ​might contain a DVC-tracked .jsonl file.​
​●​ ​models/​: The README.md inside this folder should link​​to the Hugging Face Hub, S3​ ​bucket, or other location where the production model is stored.​

### 📓​ notebooks/​

​Notebooks are for​​exploration, prototyping, and analysis​—not​​ production.​

​●​ ​Naming:​​Use a numbered prefix (e.g., 01_data_exploration.ipynb)​​to tell a story.​
​●​ ​The "Notebook to Production" Workflow:​
​1.​ ​Prototype:​​Develop your logic (e.g., a new regex for​​extractor.py) in​ ​02_preprocessing_dev.ipynb.​
​2.​ ​Refactor:​​Once the logic is stable, copy it into the​​ appropriate .py file in​ ​src/preprocessing/.​
​3.​ ​Test:​​ Write a formal unit test for your new function​​in tests/test_preprocessing.py.​
​4.​ ​Commit:​​Your notebook (with its outputs) can be committed as a record of the​ ​experiment, but the​​production logic​​now lives in​​ src/ and is covered by tests.​

### 🏛️​ alembic/ & alembic.ini​

​This is our​​database schema version control​. Just​​as we use Git to manage changes to our​
​code, we use Alembic to manage changes to our Postgres database schema.​

​●​ ​alembic/versions/​: Contains migration scripts (e.g.,​​001_add_risk_table.py).​
​●​ ​Makefile Commands:​

​○​ ​make db-migration M="your message": Auto-generates a new migration script based​ ​on changes in src/storage/schemas/postgres_schemas.py.​
​○​ ​make db-upgrade: Applies any pending migrations to the database.​

## ​3. Key Workflows in Practice​

### ​Workflow: Data Ingestion & Preprocessing​

​This example shows how the src/ modules work together as a pipeline.​

​1.​ ​Orchestrator (main.py)​: Gets its work queue by calling​ ​src.storage.mongo_repo.get_filings_to_process().​
​2.​ ​Fetch Data​: For a given filing, it fetches the raw​​HTML from S3/MinIO.​
​3.​ ​Parse (parser.py)​: The raw HTML is passed to parser.parse_filing().​
​4.​ ​Extract (extractor.py)​: The parsed object is passed​​to extractor.find_risk_section() to​ ​get the specific HTML blob.​
​5.​ ​Clean (cleaning.py)​: The blob is passed to cleaning.clean_html_blob()​​to get clean text.​
​6.​ ​Segment (segmenter.py)​: The clean text is passed to​​segmenter.split_into_risks() to get​ ​a list[str].​
​7.​ ​Analyze (analysis/inference.py)​: This list is passed​​to the analysis engine, which loads​ ​the fine-tuned model and generates embeddings and categories for each risk.​
​8.​ ​Save Results (storage/postgres_repo.py)​: The pipeline​​calls​ ​postgres_repo.insert_risk_factor() for each processed risk, saving the text, embedding,​ ​and category to Postgres.​
​9.​ ​Update Status (storage/mongo_repo.py)​: The pipeline​​calls​ ​mongo_repo.update_filing_status() to mark the filing as "processed" in MongoDB.​

​This modular structure allows each step to be tested, updated, and even run as a separate​ ​microservice.​

