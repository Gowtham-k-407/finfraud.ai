# TRACE — AI-Powered Financial Crime Network Investigator

**TRACE** (*Transaction Relationship & Crime Engine*) is an end-to-end Financial Intelligence Unit (FIU) investigation workstation built for discovering, visualizing, and reasoning about coordinated financial-crime networks across accounts, transactions, devices, and IP infrastructure.

---

## Key Capabilities

1. **Chunked Large-Dataset Ingestion & Provenance (`backend/app/ingestion/`)**
   - Processes multi-hundred-megabyte CSV datasets (verified on the 155.6 MB Kaggle `aryan208/financial-transactions-dataset-for-fraud-detection` dataset) via chunked Pandas validation and writes fast analytical Parquet caches (`datasets/processed/transactions.parquet`).
   - Quarantines malformed timestamps, non-positive amounts, missing identifiers, self-loops, and duplicate transaction IDs.
   - Explicitly separates `REAL DATASET` records from `SYNTHETIC SCENARIO` typology records throughout the API and UI, and supports live custom CSV uploads (`POST /api/datasets/upload`).

2. **Conservative Entity Resolution & Heterogeneous NetworkX Graph (`backend/app/graph_engine/`)**
   - Namespaced heterogeneous entities: `ACCOUNT:<id>`, `DEVICE:<id>`, `IP:<id>`.
   - Preserves directed multi-edge transfer flows (`nx.MultiDiGraph`), aggregated directed topology (`nx.DiGraph`), multi-hop ego-network expansion (1–3 hops), directed & infrastructure path discovery, sampled betweenness centrality, and greedy modularity community clusters.
   - Treats shared devices and shared IPs as **session evidence edges**, never blindly merging accounts.

3. **7 Explainable Financial-Crime Pattern Detectors (`backend/app/pattern_detection/`)**
   - **Multi-Hop Layering & Rapid Pass-Through** (`RAPID_PASS_THROUGH`)
   - **Fan-In Collection / Structuring Hubs** (`FAN_IN`)
   - **Fan-Out Dispersion Hubs** (`FAN_OUT`)
   - **Circular Wash / Round-Tripping Loops** (`CIRCULAR_FLOW`)
   - **Shared Device Fingerprint Clusters** (`SHARED_DEVICE`)
   - **Shared IP / Proxy vs. Benign Corporate NAT Differentiation** (`SHARED_IP`)
   - **Potential Mule-Account Indicators** (`MULE_ACCOUNT_INDICATOR`)

4. **Unsupervised Isolation Forest & Explainable Hybrid Risk (`backend/app/anomaly_detection/`)**
   - `scikit-learn` `IsolationForest` trained strictly unsupervised (zero label leakage) on 10 behavioral/telemetry features including robust Median/MAD amount deviation, velocity, off-hours activity, and device/IP reuse.
   - Transparent 4-factor hybrid risk breakdown (`Graph Typology 40%`, `Isolation Forest 25%`, `Shared Infrastructure 20%`, `Centrality & Velocity 15%`).

5. **Competing-Hypothesis AI Investigation Workbench (`backend/app/investigation_agent/`)**
   - Clearly separates **Verified Direct Ledger/Session Facts** (`EV-TX-*`, `EV-INFRA-*`) from **Analytical Inferences** (`EV-PAT-*`, `EV-ML-*`).
   - Evaluates **Suspicious Typology Hypotheses** side-by-side against **Benign Operational Alternatives** with supporting, contradicting, and missing KYC evidence, human analyst verdicts (`Corroborate` / `Reject`), audit notes, and FIU Case escalation.
   - Works out-of-the-box via its Deterministic Evidence-Grounded Engine, and automatically activates grounded Gemini (`GEMINI_API_KEY`) or OpenAI (`OPENAI_API_KEY`) synthesis when configured.

---

## Quick Start (Local Execution)

### 1. Start the FastAPI Backend (Port `8050`)

From the repository root (`c:\Users\mmall\OneDrive\Desktop\tcs`):

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8050
```

Interactive OpenAPI docs are available at `http://127.0.0.1:8050/docs`.

### 2. Start the React + Vite Workstation Frontend (Port `5175`)

In a second terminal:

```powershell
npm run dev --prefix frontend
```

Open `http://localhost:5175` in your browser.

### 3. Run Automated Verification & Production Build

```powershell
# Backend end-to-end test suite
$env:PYTHONPATH = "backend"
.\.venv\Scripts\pytest.exe backend/tests/test_end_to_end.py -v

# Frontend TypeScript & Vite production build
npm run build --prefix frontend
```

---

## Live Hackathon Demo Sequence (3 Minutes)

1. **Command Centre (`/`)**: Review live ingested transaction count, real-vs-synthetic provenance split, temporal anomaly chart, and top detected suspicious networks.
2. **Network Explorer (`/network`)**:
   - Click **"Mule Layering Chain"** in the Quick Focus bar to inspect `ACC_MULE_7701` receiving structured inflows from 5 smurf accounts and rapidly relaying ~$23k across `ACC_RELAY_7702 -> ACC_RELAY_7703 -> ACC_EXIT_7704`, while exposing covert shared device `DEV_SHADOW_901` (Orange square) bridging Hop 1 and Hop 3.
   - Use **Trace Path** (`ACC_FEED_7101` → `ACC_EXIT_7704`) to highlight the 4-hop money trail in gold.
   - Click **"Benign Office NAT (Control)"** (`203.0.113.10`) to demonstrate how TRACE scores legitimate shared corporate office IPs as **LOW** risk rather than generating false accusations.
3. **Investigation Workspace (`/investigations`)**:
   - Click **"Generate Investigation Report"** from `ACC_MULE_7701` to inspect separated Verified Facts (`[EV-TX-01]`, `[EV-INFRA-01]`) vs. Analytical Signals (`[EV-PAT-01]`), corroborate/reject competing hypotheses, append an analyst note, and click **"Escalate to FIU Case"**.
4. **Cases & Data Management (`/cases`, `/data`)**:
   - Transition case disposition (`OPEN` -> `IN_REVIEW` -> `ESCALATED`) with immutable audit trail entries, or upload `datasets/demo/trace_demo_transactions.csv` (or switch to `Real Kaggle Dataset Only`) to rebuild the entire graph and retrain Isolation Forest live.
