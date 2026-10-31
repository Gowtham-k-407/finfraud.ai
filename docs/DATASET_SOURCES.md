# Dataset Sources, Provenance & Quality Limitations

## 1. Primary Dataset — Kaggle Financial Transactions Dataset for Fraud Detection
- **Source**: `aryan208/financial-transactions-dataset-for-fraud-detection` (Kaggle, cached via `kagglehub`, ~155.6 MB CSV).
- **Verified Schema (18 Columns)**:
  `transaction_id`, `timestamp`, `sender_account`, `receiver_account`, `amount`, `transaction_type`, `merchant_category`, `location`, `device_used`, `is_fraud`, `fraud_type`, `time_since_last_transaction`, `spending_deviation_score`, `velocity_score`, `geo_anomaly_score`, `payment_channel`, `ip_address`, `device_hash`.
- **Observed Data Characteristics & Limitations**:
  - Contains realistic transaction attributes, timestamps, velocity/geo scores, device hashes, and IP addresses.
  - Across arbitrary slices, account/IP identifiers are relatively sparse (high cardinality); naive random sampling loses multi-transaction entity overlap.
- **Ingestion Strategy in TRACE**:
  - Chunked Pandas scanner (`75,000` rows/chunk) validates timestamps, positive amounts, required identifiers, and quarantines duplicates/self-loops.
  - Graph-preserving 2-pass selection retains multi-transaction overlapping accounts, real shared-device clusters (340+ real shared devices discovered!), and `is_fraud=True` records alongside organic baseline transactions, storing output in `datasets/processed/transactions.parquet`.
  - Tagged explicitly with `is_synthetic = False` and `data_source = "kaggle_real"`.

## 2. Controlled Synthetic Financial-Crime Network Scenarios
- **Purpose**: Provide verifiable ground-truth multi-hop network typologies and a benign false-positive control cluster for deterministic testing and live demonstration.
- **Explicit Provenance Tagging**: Every synthetic record carries `is_synthetic = True`, `data_source = "synthetic_typology"`, and `scenario_tag`, and displays a `SYNTHETIC SCENARIO` badge in the UI (never mixed silently with real records; users can filter or reprocess `Real Kaggle Dataset Only` at any time).
- **Included Scenarios**:
  1. `SCEN-01-MULE-LAYERING`: 5 smurf feeders -> `ACC_MULE_7701` -> `ACC_RELAY_7702` -> `ACC_RELAY_7703` -> `ACC_EXIT_7704` (rapid pass-through + covert shared device `DEV_SHADOW_901`).
  2. `SCEN-02-AGGREGATOR-HUB`: 6 structured inflows into `ACC_HUB_4400` followed by 5 rapid fan-out payouts.
  3. `SCEN-03-CIRCULAR-RING`: 4-account closed round-tripping wash loop (`ACC_RING_301..304`) sharing proxy IP `185.220.101.52`.
  4. `SCEN-04-DEVICE-FARM`: 4 accounts operating from identical emulator fingerprint `DEV_EMU_X88`.
  5. `SCEN-05-BENIGN-CORP-NAT`: 4 legitimate business accounts sharing corporate office NAT IP `203.0.113.10` with unique laptops and normal business-hours ACH utility payments (demonstrating conservative low-risk entity resolution).

## 3. Complementary Open AML Datasets Evaluated
- **PaySim**: Mobile-money synthetic simulator (`CASH_IN`, `TRANSFER`, `CASH_OUT`); lacks device/IP session telemetry.
- **IBM AMLSim / HI-Small**: Rich multi-hop laundering typologies (fan-in, fan-out, cycle, bipartite), compatible via our custom CSV uploader (`POST /api/datasets/upload`).
- **Elliptic Bitcoin Dataset**: Pseudo-anonymous UTXO graph with anonymized features (`1..166`), lacking interpretable banking/device/IP semantics for human FIU narrative explanations.

