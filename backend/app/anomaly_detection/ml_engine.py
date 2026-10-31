"""
Unsupervised Behavioral Anomaly Engine (scikit-learn Isolation Forest)
& Transparent Hybrid Multi-Signal Risk Aggregator.

Key engineering safeguards:
  - Strictly unsupervised training: `is_fraud` labels are NEVER fed into IsolationForest.
  - Chronological split evaluation when ground-truth `is_fraud` exists in dataset.
  - Robust median/MAD z-score baseline + velocity + infrastructure reuse features.
  - Normalized component scores [0..100] with explicit weighted contributions.
"""
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

from app.core.config import ISOLATION_FOREST_PATH
from app.graph_engine.builder import FinancialGraphEngine
from app.schemas.models import PatternDetection

FEATURE_COLUMNS = [
    "log_amount",
    "amount_mad_z",
    "spending_deviation_score",
    "velocity_score",
    "geo_anomaly_score",
    "is_off_hours",
    "sender_tx_count",
    "receiver_tx_count",
    "device_account_reuse",
    "ip_account_reuse",
]


class AnomalyAndRiskEngine:
    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=120,
            contamination=0.045,
            random_state=42,
            n_jobs=1,
        )
        self.model_metadata: Dict[str, Any] = {}
        self.tx_anomaly_scores: Dict[str, float] = {}
        self.acct_anomaly_scores: Dict[str, float] = {}

    def fit_and_score(
        self,
        df: pd.DataFrame,
        graph_engine: FinancialGraphEngine,
        detections: List[PatternDetection],
    ) -> Dict[str, Any]:
        if df.empty:
            return {}

        work = df.copy()
        amounts = work["amount"].astype(float).values
        work["log_amount"] = np.log1p(np.maximum(amounts, 0.0))

        # Robust Median / MAD amount baseline (adopted from Repo A best practice)
        med = float(np.median(amounts))
        mad = float(np.median(np.abs(amounts - med))) or 1.0
        work["amount_mad_z"] = np.clip(0.6745 * (amounts - med) / mad, -10.0, 25.0)

        ts_parsed = pd.to_datetime(work["timestamp"], errors="coerce")
        hours = ts_parsed.dt.hour.fillna(12)
        work["is_off_hours"] = ((hours <= 4) | (hours >= 23)).astype(float)

        s_counts = work["sender_account"].value_counts()
        r_counts = work["receiver_account"].value_counts()
        work["sender_tx_count"] = work["sender_account"].map(s_counts).fillna(1).astype(float)
        work["receiver_tx_count"] = work["receiver_account"].map(r_counts).fillna(1).astype(float)

        dev_reuse = {
             dev.split(":", 1)[1]: len(accts)
            for dev, accts in graph_engine.device_to_accounts.items()
        }
        ip_reuse = {
            ip.split(":", 1)[1]: len(accts)
            for ip, accts in graph_engine.ip_to_accounts.items()
        }
        work["device_account_reuse"] = work["device_hash"].map(dev_reuse).fillna(1).astype(float)
        work["ip_account_reuse"] = work["ip_address"].map(ip_reuse).fillna(1).astype(float)

        X = work[FEATURE_COLUMNS].fillna(0.0).values

        # Chronological 75/25 split for leak-free unsupervised fit & evaluation
        n_total = len(work)
        split_idx = max(int(n_total * 0.75), min(100, n_total))
        X_train = X[:split_idx]

        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        self.model.fit(X_train_scaled)

        X_all_scaled = self.scaler.transform(X)
        # decision_function: lower/negative = more anomalous. Invert & normalize to [0, 100]
        raw_decision = -self.model.decision_function(X_all_scaled)
        preds_binary = (self.model.predict(X_all_scaled) == -1).astype(int)

        p5, p99 = float(np.percentile(raw_decision, 5)), float(np.percentile(raw_decision, 99.5))
        span = max(p99 - p5, 1e-6)
        norm_scores = np.clip(((raw_decision - p5) / span) * 100.0, 0.0, 100.0)

        work["ml_anomaly_score"] = np.round(norm_scores, 1)
        work["ml_is_anomaly"] = preds_binary.astype(bool)

        # Update graph_engine dataframe & tx_lookup with ML anomaly scores
        graph_engine.df["ml_anomaly_score"] = work["ml_anomaly_score"].values
        graph_engine.df["ml_is_anomaly"] = work["ml_is_anomaly"].values
        self.tx_anomaly_scores = dict(zip(work["transaction_id"], work["ml_anomaly_score"]))
        for tid, sc in self.tx_anomaly_scores.items():
            if tid in graph_engine.tx_lookup:
                graph_engine.tx_lookup[tid]["ml_anomaly_score"] = float(sc)
                graph_engine.tx_lookup[tid]["ml_is_anomaly"] = bool(sc >= 72.0)

        # Aggregate max/top-mean anomaly score per account
        acct_scores: Dict[str, List[float]] = defaultdict(list)
        for s_raw, r_raw, sc in zip(
            work["sender_account"], work["receiver_account"], work["ml_anomaly_score"]
        ):
            acct_scores[f"ACCOUNT:{s_raw}"].append(float(sc))
            acct_scores[f"ACCOUNT:{r_raw}"].append(float(sc) * 0.85)

        self.acct_anomaly_scores = {
            aid: round(0.65 * max(vals) + 0.35 * float(np.mean(vals)), 1)
            for aid, vals in acct_scores.items()
        }

        # Persist model artifact via joblib
        joblib.dump(
            {
                "scaler": self.scaler,
                "model": self.model,
                "features": FEATURE_COLUMNS,
                "version": "iforest-v1.2-unsupervised",
            },
            ISOLATION_FOREST_PATH,
        )

        # Evaluate on chronological holdout test slice ONLY if ground-truth labels exist
        eval_metrics: Dict[str, Any] = {"evaluation_available": False}
        y_true_test = work["is_fraud"].astype(int).values[split_idx:]
        if len(y_true_test) > 20 and int(y_true_test.sum()) >= 2:
            y_pred_test = preds_binary[split_idx:]
            y_score_test = norm_scores[split_idx:] / 100.0
            tn, fp, fn, tp = confusion_matrix(y_true_test, y_pred_test, labels=[0, 1]).ravel()
            eval_metrics = {
                "evaluation_available": True,
                "split_strategy": "Chronological 75% Train / 25% Holdout Test (Zero Label Leakage)",
                "test_records": int(len(y_true_test)),
                "test_positive_labels": int(y_true_test.sum()),
                "precision": round(float(precision_score(y_true_test, y_pred_test, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true_test, y_pred_test, zero_division=0)), 4),
                "f1_score": round(float(f1_score(y_true_test, y_pred_test, zero_division=0)), 4),
                "pr_auc": round(float(average_precision_score(y_true_test, y_score_test)), 4),
                "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
                "caveat": (
                    "Isolation Forest is strictly unsupervised behavioral anomaly detection. "
                    "Dataset `is_fraud` flags reflect transaction/scenario labels, not adjudicated criminal guilt."
                ),
            }

        self._compute_hybrid_entity_risk(graph_engine, detections)

        self.model_metadata = {
            "model_name": "IsolationForest Behavioral Anomaly Detector",
            "model_version": "iforest-v1.2-unsupervised",
            "artifact_path": str(ISOLATION_FOREST_PATH),
            "feature_count": len(FEATURE_COLUMNS),
            "features": FEATURE_COLUMNS,
            "train_rows": int(len(X_train)),
            "scored_rows": int(n_total),
            "anomalous_transactions_flagged": int(preds_binary.sum()),
            "anomaly_rate_pct": round(float(preds_binary.mean() * 100.0), 2),
            "hybrid_weights": {
                "graph_pattern_evidence": 0.40,
                "isolation_forest_anomaly": 0.25,
                "shared_infrastructure_telemetry": 0.20,
                "topological_centrality_velocity": 0.15,
            },
            "evaluation": eval_metrics,
        }
        return self.model_metadata

    def _compute_hybrid_entity_risk(
        self,
        graph_engine: FinancialGraphEngine,
        detections: List[PatternDetection],
    ) -> None:
        # Index detections per entity
        det_by_entity: Dict[str, List[PatternDetection]] = defaultdict(list)
        for det in detections:
            for ent in det.involved_entities:
                det_by_entity[ent].append(det)

        max_bet = max(graph_engine.betweenness_map.values(), default=0.001) or 0.001

        for aid, st in graph_engine.account_stats.items():
            ent_dets = det_by_entity.get(aid, [])
            pattern_types = sorted({d.pattern_type for d in ent_dets})

            # 1. Graph Pattern Score [0..100] (weight 0.40)
            non_infra_dets = [
                d for d in ent_dets if d.pattern_type not in ("SHARED_DEVICE", "SHARED_IP")
            ]
            if non_infra_dets:
                pattern_score = min(
                    100.0,
                    max(d.risk_score for d in non_infra_dets) + 4.0 * (len(non_infra_dets) - 1),
                )
            else:
                pattern_score = 0.0

            # 2. Isolation Forest Behavioral Anomaly Score [0..100] (weight 0.25)
            ml_score = float(self.acct_anomaly_scores.get(aid, 10.0))

            # 3. Shared Infrastructure Telemetry Score [0..100] (weight 0.20)
            infra_dets = [d for d in ent_dets if d.pattern_type in ("SHARED_DEVICE", "SHARED_IP")]
            infra_score = max((d.risk_score for d in infra_dets), default=0.0)

            # 4. Topological Centrality & Counterparty Velocity [0..100] (weight 0.15)
            bet_norm = min(100.0, (graph_engine.betweenness_map.get(aid, 0.0) / max_bet) * 75.0)
            tx_vel_norm = min(100.0, st["total_tx_count"] * 9.0)
            topo_score = round(0.5 * bet_norm + 0.5 * tx_vel_norm, 1)

            composite = (
                0.40 * pattern_score
                + 0.25 * ml_score
                + 0.20 * infra_score
                + 0.15 * topo_score
            )
            # Ensure primary targets of CRITICAL multi-signal patterns reflect appropriate priority
            if any(d.primary_entity == aid and d.severity == "CRITICAL" for d in non_infra_dets):
                composite = max(composite, 78.0)
            elif non_infra_dets and max(d.risk_score for d in non_infra_dets) >= 85.0:
                composite = max(composite, 68.0)

            composite = round(min(99.0, composite), 1)
            if composite >= 75.0:
                priority = "CRITICAL"
            elif composite >= 55.0:
                priority = "HIGH"
            elif composite >= 32.0:
                priority = "MEDIUM"
            else:
                priority = "LOW"

            contributions = [
                {
                    "factor": "Graph Typology Patterns",
                    "raw_score": round(pattern_score, 1),
                    "weight": 0.40,
                    "weighted_points": round(0.40 * pattern_score, 1),
                    "detail": (
                        f"{len(non_infra_dets)} network typology finding(s): {', '.join(pattern_types) or 'None'}"
                    ),
                },
                {
                    "factor": "Isolation Forest Behavioral Anomaly",
                    "raw_score": round(ml_score, 1),
                    "weight": 0.25,
                    "weighted_points": round(0.25 * ml_score, 1),
                    "detail": "Unsupervised deviation across amount MAD, velocity, off-hours & reuse.",
                },
                {
                    "factor": "Shared Device / IP Telemetry",
                    "raw_score": round(infra_score, 1),
                    "weight": 0.20,
                    "weighted_points": round(0.20 * infra_score, 1),
                    "detail": (
                        f"{len(infra_dets)} shared infrastructure cluster(s) observed."
                        if infra_dets
                        else "No multi-account device or IP collision."
                    ),
                },
                {
                    "factor": "Network Centrality & Activity",
                    "raw_score": round(topo_score, 1),
                    "weight": 0.15,
                    "weighted_points": round(0.15 * topo_score, 1),
                    "detail": f"{st['total_tx_count']} transfers (${st['total_volume']:,.2f} total flow).",
                },
            ]

            graph_engine.entity_risk[aid] = {
                "risk_score": composite,
                "priority": priority,
                "ml_anomaly_score": round(ml_score, 1),
                "pattern_types": pattern_types,
                "detection_count": len(ent_dets),
                "evidence_quality": "HIGH" if len(ent_dets) >= 2 else ("MODERATE" if ent_dets else "BASELINE"),
                "model_version": "hybrid-risk-v1.2 (iforest + nx-typology)",
                "contributions": contributions,
            }
