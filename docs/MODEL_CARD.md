# Model Card & Epistemic Limitations — TRACE Analytics Engine

## 1. Isolation Forest Behavioral Anomaly Model (`iforest-v1.2-unsupervised`)
- **Algorithm**: `scikit-learn` `IsolationForest(n_estimators=120, contamination=0.045, random_state=42)` preceded by `StandardScaler`.
- **Leak-Free Training Discipline**:
  - Trained strictly unsupervised on a chronological 75% training split.
  - `is_fraud` labels are **never** included in feature engineering or model fitting.
- **10 Behavioral & Telemetry Features**:
  `log_amount`, `amount_mad_z` (robust Median/MAD baseline), `spending_deviation_score`, `velocity_score`, `geo_anomaly_score`, `is_off_hours`, `sender_tx_count`, `receiver_tx_count`, `device_account_reuse`, `ip_account_reuse`.

## 2. Hybrid Multi-Signal Entity Risk Aggregation (`hybrid-risk-v1.2`)
Normalized `[0..100]` weighted composite score:
- **40%** — Graph Typology Detections (Layering/Pass-Through, Circular Rings, Fan-In, Fan-Out, Mule Indicators)
- **25%** — Isolation Forest Behavioral Anomaly Score
- **20%** — Shared Device / Shared IP Telemetry Risk
- **15%** — Topological Betweenness Centrality & Transaction Velocity

## 3. Mandatory Limitations & Safeguards
1. **Not a Calibrated Criminal Probability**: Scores rank investigative review priority (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), not legal guilt.
2. **Infrastructure Sharing != Common Ownership**: Shared IP addresses occur routinely under corporate NAT, mobile carrier CGNAT, and public Wi-Fi. TRACE explicitly differentiates low-velocity multi-device NAT sharing from high-velocity proxy coordination.
3. **Human-in-the-Loop Mandate**: The platform never auto-freezes accounts, accuses customers, or files regulatory SARs automatically. Every AI/deterministic investigation report includes competing benign hypotheses and missing KYC evidence checklists.

