import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"
DATASETS_DIR = BASE_DIR / "datasets"
RAW_DATA_DIR = DATASETS_DIR / "raw"
PROCESSED_DATA_DIR = DATASETS_DIR / "processed"
DEMO_DATA_DIR = DATASETS_DIR / "demo"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
REPORTS_DIR = ARTIFACTS_DIR / "reports"

for directory in [
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    DEMO_DATA_DIR,
    MODELS_DIR,
    REPORTS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

PARQUET_PATH = PROCESSED_DATA_DIR / "transactions.parquet"
QUARANTINE_PATH = PROCESSED_DATA_DIR / "quarantined_records.parquet"
SQLITE_DB_PATH = PROCESSED_DATA_DIR / "trace_investigator.db"
ISOLATION_FOREST_PATH = MODELS_DIR / "isolation_forest.joblib"
DEMO_CSV_PATH = DEMO_DATA_DIR / "trace_demo_transactions.csv"

KAGGLE_CACHE_CANDIDATE = (
    Path.home()
    / ".cache"
    / "kagglehub"
    / "datasets"
    / "aryan208"
    / "financial-transactions-dataset-for-fraud-detection"
    / "versions"
    / "1"
    / "financial_fraud_detection_dataset.csv"
)

DEFAULT_KAGGLE_SAMPLE_LIMIT = int(os.getenv("TRACE_MAX_ROWS", "6000"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
