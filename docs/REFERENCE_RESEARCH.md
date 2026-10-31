# Reference Repository Research & Architectural Decisions

## 1. Repository A — `mominalix/AI-Based-Anti-Money-Laundering-AML-System`
- **Core Capabilities Studied**: Hybrid rule + statistical risk scoring, robust Median/MAD amount deviation baselines, temporal velocity checks (fan-in, fan-out, rapid pass-through, reciprocal transfers), NetworkX centrality/community analysis, evidence snapshots, and human-in-the-loop analyst case review with optional LLM narrative drafting.
- **Limitations Identified**: Microservice separation decouples graph topology analysis from primary risk scoring.
- **Adopted Conceptually in TRACE**:
  - Robust Median / Median Absolute Deviation (`0.6745 * (x - median) / MAD`) z-score feature inside our behavioral anomaly pipeline.
  - Integrated NetworkX topology directly into primary hybrid risk evaluation (40% graph typology weight) rather than treating graph analytics as an isolated post-hoc report.
  - Evidence-ID traceability (`EV-TX-*`, `EV-INFRA-*`, `EV-PAT-*`) and human analyst case audit trails.

## 2. Repository B — `ali7832/financial-anomaly-fraud-system`
- **Core Capabilities Studied**: Monolithic FastAPI service design, `scikit-learn` `IsolationForest` unsupervised anomaly detection, `joblib` model persistence, configurable scoring weights, suspicious-decision audit logging, synthetic scenario generation, and React + Vite analyst UI patterns with clean API fallback handling.
- **Adopted Conceptually in TRACE**:
  - Modular FastAPI monolith with `StandardScaler` + `IsolationForest` persisted via `joblib` (`artifacts/models/isolation_forest.joblib`).
  - Explicit multi-factor hybrid risk contribution breakdown (`risk.contributions`) exposed to the React/Vite workstation.

## 3. Repository C — `mwasifanwar/finrisk-predictor`
- **Core Capabilities Studied**: Graph-centric relationship representation, behavioral profiling, temporal flow analysis, and network risk visualization concepts.
- **Verification & Engineering Decision**:
  - Heavy deep-learning GNN pipelines add substantial training latency and opaque black-box scoring unsuited to explainable FIU case review.
  - Instead, TRACE prioritizes transparent NetworkX multi-edge directed flow traversal, exact cycle/chain reconstruction, sampled betweenness centrality, greedy modularity community clustering, and competing-hypothesis reasoning.

