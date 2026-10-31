# Datasets Directory Structure

- `raw/` — User-uploaded CSV datasets via `POST /api/datasets/upload` (excluded from Git via `.gitignore`). Automatically falls back to the locally cached Kaggle dataset `aryan208/financial-transactions-dataset-for-fraud-detection` (`~/.cache/kagglehub/...`).
- `processed/` — Generated cleaned Parquet analytical cache (`transactions.parquet`), quarantined invalid rows (`quarantined_records.parquet`), and local SQLite persistence (`trace_investigator.db`).
- `demo/trace_demo_transactions.csv` — Lightweight portable demo CSV combining real dataset transactions (`is_synthetic=False`) with controlled multi-hop financial-crime network scenarios (`is_synthetic=True`, tagged by `scenario_tag`).

