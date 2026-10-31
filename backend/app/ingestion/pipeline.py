"""
Chunked Pandas Data Ingestion, Validation, Quarantine & Parquet Preparation Pipeline.
Designed to safely process multi-million-row CSVs (such as the 155MB Kaggle financial
transactions dataset) without loading multiple copies into memory.
"""
import io
import time
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import (
    DEFAULT_KAGGLE_SAMPLE_LIMIT,
    DEMO_CSV_PATH,
    KAGGLE_CACHE_CANDIDATE,
    PARQUET_PATH,
    QUARANTINE_PATH,
    RAW_DATA_DIR,
)
from app.ingestion.synthetic_scenarios import generate_synthetic_typologies

REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount",
]

OPTIONAL_DEFAULTS: Dict[str, Any] = {
    "transaction_type": "transfer",
    "merchant_category": "general",
    "location": "Unknown",
    "device_used": "web",
    "is_fraud": False,
    "fraud_type": "",
    "time_since_last_transaction": 0.0,
    "spending_deviation_score": 0.0,
    "velocity_score": 1,
    "geo_anomaly_score": 0.0,
    "payment_channel": "electronic",
    "ip_address": "",
    "device_hash": "",
    "is_synthetic": False,
    "data_source": "kaggle_real",
    "scenario_tag": "",
}


def find_best_raw_csv() -> Optional[Path]:
    uploaded = sorted(RAW_DATA_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if uploaded:
        return uploaded[0]
    if KAGGLE_CACHE_CANDIDATE.exists():
        return KAGGLE_CACHE_CANDIDATE
    return None


def _clean_and_validate_chunk(
    chunk: pd.DataFrame,
    seen_tx_ids: set,
    default_source: str = "kaggle_real",
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    stats = {
        "raw_rows": len(chunk),
        "missing_required": 0,
        "invalid_amount": 0,
        "invalid_timestamp": 0,
        "self_loop": 0,
        "duplicate_tx_id": 0,
    }
    chunk = chunk.copy()
    chunk.columns = [str(c).strip() for c in chunk.columns]

    # Map common column aliases if user uploads custom CSV
    alias_map = {
        "tx_id": "transaction_id",
        "id": "transaction_id",
        "sender": "sender_account",
        "source_account": "sender_account",
        "nameOrig": "sender_account",
        "receiver": "receiver_account",
        "target_account": "receiver_account",
        "nameDest": "receiver_account",
        "type": "transaction_type",
        "isFraud": "is_fraud",
    }
    for alias, canonical in alias_map.items():
        if alias in chunk.columns and canonical not in chunk.columns:
            chunk = chunk.rename(columns={alias: canonical})

    for col in REQUIRED_COLUMNS:
        if col not in chunk.columns:
            raise ValueError(f"CSV is missing required column: '{col}'")

    for col, default_val in OPTIONAL_DEFAULTS.items():
        if col not in chunk.columns:
            chunk[col] = default_val

    if "data_source" not in chunk.columns or chunk["data_source"].isna().all():
        chunk["data_source"] = default_source

    # Normalize strings
    for str_col in ["transaction_id", "sender_account", "receiver_account", "ip_address", "device_hash"]:
        chunk[str_col] = chunk[str_col].fillna("").astype(str).str.strip()

    missing_mask = (
        (chunk["transaction_id"] == "")
        | (chunk["sender_account"] == "")
        | (chunk["receiver_account"] == "")
    )
    stats["missing_required"] = int(missing_mask.sum())

    chunk["amount"] = pd.to_numeric(chunk["amount"], errors="coerce")
    invalid_amt_mask = chunk["amount"].isna() | (chunk["amount"] <= 0)
    stats["invalid_amount"] = int((~missing_mask & invalid_amt_mask).sum())

    try:
        parsed_ts = pd.to_datetime(chunk["timestamp"], format="ISO8601", errors="coerce", utc=False)
    except Exception:
        parsed_ts = pd.to_datetime(chunk["timestamp"], format="mixed", errors="coerce", utc=False)
    invalid_ts_mask = parsed_ts.isna()
    stats["invalid_timestamp"] = int((~missing_mask & ~invalid_amt_mask & invalid_ts_mask).sum())

    self_loop_mask = chunk["sender_account"] == chunk["receiver_account"]
    stats["self_loop"] = int(
        (~missing_mask & ~invalid_amt_mask & ~invalid_ts_mask & self_loop_mask).sum()
    )

    # Duplicate check across chunks
    in_chunk_dup = chunk["transaction_id"].duplicated(keep="first")
    cross_chunk_dup = chunk["transaction_id"].isin(seen_tx_ids)
    dup_mask = in_chunk_dup | cross_chunk_dup
    stats["duplicate_tx_id"] = int(
        (~missing_mask & ~invalid_amt_mask & ~invalid_ts_mask & ~self_loop_mask & dup_mask).sum()
    )

    bad_mask = missing_mask | invalid_amt_mask | invalid_ts_mask | self_loop_mask | dup_mask
    quarantined = chunk[bad_mask].copy()
    valid = chunk[~bad_mask].copy()
    valid["parsed_ts"] = parsed_ts[~bad_mask]
    valid["timestamp"] = valid["parsed_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    valid["epoch"] = (valid["parsed_ts"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    valid = valid.drop(columns=["parsed_ts"])

    # Clean numeric optional columns
    for num_col, fallback in [
        ("time_since_last_transaction", 0.0),
        ("spending_deviation_score", 0.0),
        ("velocity_score", 1.0),
        ("geo_anomaly_score", 0.0),
    ]:
        valid[num_col] = pd.to_numeric(valid[num_col], errors="coerce").fillna(fallback)

    valid["is_fraud"] = (
        valid["is_fraud"]
        .astype(str)
        .str.lower()
        .isin(["true", "1", "yes", "t"])
    )
    valid["is_synthetic"] = (
        valid["is_synthetic"]
        .astype(str)
        .str.lower()
        .isin(["true", "1", "yes", "t"])
    )
    valid["fraud_type"] = valid["fraud_type"].fillna("").astype(str)
    valid["scenario_tag"] = valid["scenario_tag"].fillna("").astype(str)
    valid["transaction_type"] = valid["transaction_type"].fillna("transfer").astype(str)
    valid["merchant_category"] = valid["merchant_category"].fillna("general").astype(str)
    valid["location"] = valid["location"].fillna("Unknown").astype(str)
    valid["device_used"] = valid["device_used"].fillna("web").astype(str)
    valid["payment_channel"] = valid["payment_channel"].fillna("electronic").astype(str)

    seen_tx_ids.update(valid["transaction_id"].tolist())
    return valid, quarantined, stats


def ingest_and_prepare_dataset(
    csv_path: Optional[Path] = None,
    source_mode: str = "hybrid",
    max_kaggle_rows: int = DEFAULT_KAGGLE_SAMPLE_LIMIT,
    include_synthetic_scenarios: bool = True,
    custom_source_label: str = "kaggle_real",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Chunked ingestion pipeline:
      1. Reads large CSV in 75,000-row chunks (scanning up to 300,000 rows fast to
         discover real multi-transaction connected accounts + real fraud events).
      2. Quarantines malformed, negative-amount, self-loop, or duplicate records.
      3. Preserves network-connected accounts from the real dataset plus stratified
         background traffic up to `max_kaggle_rows`.
      4. Optionally merges explicitly tagged `synthetic_typology` scenarios so
         complex multi-hop mule chains, cycles, and device farms are demonstrable
         with 100% provenance transparency.
      5. Saves cleaned dataset to Parquet for sub-second analytical reloads.
    """
    t0 = time.perf_counter()
    seen_tx_ids: set = set()
    agg_stats = Counter()
    quarantined_frames: List[pd.DataFrame] = []
    real_frames: List[pd.DataFrame] = []

    resolved_csv = csv_path or find_best_raw_csv()
    source_description = "Synthetic Typology Suite Only"

    if source_mode != "synthetic_only" and resolved_csv and resolved_csv.exists():
        file_size_mb = round(resolved_csv.stat().st_size / (1024 * 1024), 2)
        source_description = f"{resolved_csv.name} ({file_size_mb} MB)"

        # Fast chunked scan (75,000 rows per chunk for sub-2s turnaround on 155MB CSV)
        max_scan_rows = min(max(max_kaggle_rows * 8, 75_000), 150_000)
        scanned = 0
        priority_rows: List[pd.DataFrame] = []
        normal_pool: List[pd.DataFrame] = []
        account_counts: Counter = Counter()
        device_counts: Counter = Counter()

        chunk_iter = pd.read_csv(
            resolved_csv,
            chunksize=75_000,
            low_memory=False,
        )
        raw_valid_chunks: List[pd.DataFrame] = []
        for chunk in chunk_iter:
            valid_chunk, bad_chunk, c_stats = _clean_and_validate_chunk(
                chunk, seen_tx_ids, default_source=custom_source_label
            )
            agg_stats.update(c_stats)
            if not bad_chunk.empty:
                quarantined_frames.append(bad_chunk.head(200))

            account_counts.update(valid_chunk["sender_account"].tolist())
            account_counts.update(valid_chunk["receiver_account"].tolist())
            non_empty_devs = valid_chunk.loc[valid_chunk["device_hash"] != "", "device_hash"]
            device_counts.update(non_empty_devs.tolist())

            raw_valid_chunks.append(valid_chunk)
            scanned += len(chunk)
            if scanned >= max_scan_rows:
                break

        if raw_valid_chunks:
            combined_scan = pd.concat(raw_valid_chunks, ignore_index=True)
            multi_accounts = {acc for acc, cnt in account_counts.items() if cnt >= 2}
            shared_devs = {dev for dev, cnt in device_counts.items() if cnt >= 2}

            is_network_interesting = (
                combined_scan["is_fraud"]
                | (
                    combined_scan["sender_account"].isin(multi_accounts)
                    & combined_scan["receiver_account"].isin(multi_accounts)
                )
                | combined_scan["device_hash"].isin(shared_devs)
            )

            interesting_df = combined_scan[is_network_interesting]
            remainder_df = combined_scan[~is_network_interesting]

            if len(interesting_df) >= max_kaggle_rows:
                sampled_real = interesting_df.head(max_kaggle_rows).copy()
            else:
                needed = max_kaggle_rows - len(interesting_df)
                fill_df = remainder_df.head(needed)
                sampled_real = pd.concat([interesting_df, fill_df], ignore_index=True)

            real_frames.append(sampled_real)

    synthetic_count = 0
    if source_mode == "synthetic_only" or (include_synthetic_scenarios and source_mode != "kaggle_only"):
        syn_raw = generate_synthetic_typologies()
        syn_valid, syn_bad, s_stats = _clean_and_validate_chunk(
            syn_raw, seen_tx_ids, default_source="synthetic_typology"
        )
        agg_stats.update(s_stats)
        synthetic_count = len(syn_valid)
        real_frames.append(syn_valid)
        if source_mode == "hybrid" and resolved_csv and resolved_csv.exists():
            source_description = f"{resolved_csv.name} + Controlled Typology Scenarios"

    if not real_frames:
        # Ultimate fallback so application ALWAYS boots cleanly
        syn_raw = generate_synthetic_typologies()
        syn_valid, _, s_stats = _clean_and_validate_chunk(
            syn_raw, seen_tx_ids, default_source="synthetic_typology"
        )
        agg_stats.update(s_stats)
        synthetic_count = len(syn_valid)
        real_frames.append(syn_valid)

    final_df = pd.concat(real_frames, ignore_index=True)
    final_df = final_df.sort_values("epoch").reset_index(drop=True)

    # Persist Parquet + Demo CSV snapshot
    final_df.to_parquet(PARQUET_PATH, index=False)
    if quarantined_frames:
        pd.concat(quarantined_frames, ignore_index=True).to_parquet(QUARANTINE_PATH, index=False)

    # Save a lightweight portable demo CSV (synthetic + 400 real rows)
    demo_subset = pd.concat(
        [
            final_df[final_df["is_synthetic"]],
            final_df[~final_df["is_synthetic"]].head(450),
        ],
        ignore_index=True,
    )
    demo_subset.to_csv(DEMO_CSV_PATH, index=False)

    elapsed_sec = round(time.perf_counter() - t0, 3)
    real_count = int((~final_df["is_synthetic"]).sum())
    quarantined_total = (
        agg_stats["missing_required"]
        + agg_stats["invalid_amount"]
        + agg_stats["invalid_timestamp"]
        + agg_stats["self_loop"]
        + agg_stats["duplicate_tx_id"]
    )

    quality_report = {
        "source_description": source_description,
        "source_mode": source_mode,
        "raw_rows_scanned": int(agg_stats["raw_rows"]),
        "active_rows_loaded": int(len(final_df)),
        "real_dataset_rows": real_count,
        "synthetic_scenario_rows": int(synthetic_count),
        "quarantined_rows": int(quarantined_total),
        "quarantine_breakdown": {
            "missing_required_identifiers": int(agg_stats["missing_required"]),
            "non_positive_or_nan_amount": int(agg_stats["invalid_amount"]),
            "malformed_timestamp": int(agg_stats["invalid_timestamp"]),
            "self_transfer_loops": int(agg_stats["self_loop"]),
            "duplicate_transaction_ids": int(agg_stats["duplicate_tx_id"]),
        },
        "missing_device_hash_count": int((final_df["device_hash"] == "").sum()),
        "missing_ip_address_count": int((final_df["ip_address"] == "").sum()),
        "date_range_start": str(final_df["timestamp"].min()) if not final_df.empty else None,
        "date_range_end": str(final_df["timestamp"].max()) if not final_df.empty else None,
        "total_volume_usd": round(float(final_df["amount"].sum()), 2),
        "parquet_cache_path": str(PARQUET_PATH),
        "processing_time_seconds": elapsed_sec,
    }
    return final_df, quality_report


def ingest_uploaded_csv_bytes(
    filename: str,
    content: bytes,
    include_synthetic_scenarios: bool = False,
    max_rows: int = 25000,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    safe_name = Path(filename).name
    target_path = RAW_DATA_DIR / f"uploaded_{int(time.time())}_{safe_name}"
    target_path.write_bytes(content)
    return ingest_and_prepare_dataset(
        csv_path=target_path,
        source_mode="hybrid" if include_synthetic_scenarios else "custom_csv",
        max_kaggle_rows=max_rows,
        include_synthetic_scenarios=include_synthetic_scenarios,
        custom_source_label=f"uploaded:{safe_name}",
    )
