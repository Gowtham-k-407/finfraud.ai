"""
Central Application State Singleton.
Coordinates dataset ingestion/caching, NetworkX graph construction, Pattern Detection,
Isolation Forest ML scoring, and initial Case/Investigation seeding.
"""
import threading
from typing import Any, Dict, List, Optional

import pandas as pd

from app.anomaly_detection.ml_engine import AnomalyAndRiskEngine
from app.core.config import DEFAULT_KAGGLE_SAMPLE_LIMIT, PARQUET_PATH
from app.graph_engine.builder import FinancialGraphEngine
from app.ingestion.pipeline import ingest_and_prepare_dataset, ingest_uploaded_csv_bytes
from app.investigation_agent.investigator import EvidenceGroundedInvestigator
from app.pattern_detection.detectors import PatternDetectorSuite
from app.schemas.models import PatternDetection
from app.storage.database import InvestigationDatabase


class ApplicationWorkspaceState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.db = InvestigationDatabase()
        self.graph_engine = FinancialGraphEngine()
        self.ml_engine = AnomalyAndRiskEngine()
        self.investigator = EvidenceGroundedInvestigator()
        self.detections: List[PatternDetection] = []
        self.quality_report: Dict[str, Any] = {}
        self.is_ready: bool = False

    def initialize(self) -> None:
        with self._lock:
            if PARQUET_PATH.exists():
                try:
                    df = pd.read_parquet(PARQUET_PATH)
                    saved_quality = self.db.get_latest_dataset_run()
                    if not df.empty and saved_quality:
                        self.quality_report = saved_quality
                        self._rebuild_analytics_unlocked(df)
                        self._seed_initial_cases_if_empty()
                        self.is_ready = True
                        return
                except Exception:
                    pass

            df, quality = ingest_and_prepare_dataset(
                source_mode="hybrid",
                max_kaggle_rows=DEFAULT_KAGGLE_SAMPLE_LIMIT,
                include_synthetic_scenarios=True,
            )
            self.quality_report = quality
            self.db.record_dataset_run(quality)
            self._rebuild_analytics_unlocked(df)
            self._seed_initial_cases_if_empty()
            self.is_ready = True

    def reprocess_dataset(
        self,
        source_mode: str = "hybrid",
        max_kaggle_rows: int = DEFAULT_KAGGLE_SAMPLE_LIMIT,
        include_synthetic_scenarios: bool = True,
    ) -> Dict[str, Any]:
        with self._lock:
            df, quality = ingest_and_prepare_dataset(
                source_mode=source_mode,
                max_kaggle_rows=max_kaggle_rows,
                include_synthetic_scenarios=include_synthetic_scenarios,
            )
            self.quality_report = quality
            self.db.record_dataset_run(quality)
            self._rebuild_analytics_unlocked(df)
            return quality

    def process_uploaded_csv(
        self,
        filename: str,
        content: bytes,
        include_synthetic_scenarios: bool = False,
        max_rows: int = 25000,
    ) -> Dict[str, Any]:
        with self._lock:
            df, quality = ingest_uploaded_csv_bytes(
                filename=filename,
                content=content,
                include_synthetic_scenarios=include_synthetic_scenarios,
                max_rows=max_rows,
            )
            self.quality_report = quality
            self.db.record_dataset_run(quality)
            self._rebuild_analytics_unlocked(df)
            return quality

    def _rebuild_analytics_unlocked(self, df: pd.DataFrame) -> None:
        self.graph_engine.build_from_dataframe(df)
        detector_suite = PatternDetectorSuite(self.graph_engine)
        self.detections = detector_suite.run_all()
        self.ml_engine.fit_and_score(df, self.graph_engine, self.detections)

    def _seed_initial_cases_if_empty(self) -> None:
        if self.db.list_cases():
            return
        if not self.detections:
            return

        # Seed an initial evidence-backed investigation & open case on top detection so UI has rich live history
        top_det = self.detections[0]
        try:
            report = self.investigator.investigate(
                target_id=top_det.primary_entity,
                target_type="ACCOUNT",
                graph_engine=self.graph_engine,
                detections=self.detections,
                use_llm_if_available=False,
            )
            self.db.save_investigation(report.model_dump())
            self.db.create_case(
                title=f"{top_det.pattern_label} — {top_det.primary_entity.split(':')[-1]}",
                primary_entity=top_det.primary_entity,
                priority=top_det.severity,
                assigned_analyst="A. Sharma (FIU Lead)",
                investigation_id=report.investigation_id,
                detection_ids=[top_det.detection_id],
                summary=top_det.summary,
            )
        except Exception:
            pass


workspace_state = ApplicationWorkspaceState()

