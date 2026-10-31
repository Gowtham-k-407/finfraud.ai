"""
Controlled Synthetic Financial-Crime Network Scenarios.
Every record generated here is explicitly flagged with:
  - is_synthetic = True
  - data_source = "synthetic_typology"
  - scenario_tag = <scenario identifier>
so investigators and UI screens always distinguish synthetic demonstration rings
from real dataset records.
"""
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd


def generate_synthetic_typologies() -> pd.DataFrame:
    base_time = datetime(2023, 11, 14, 9, 15, 0)
    rows: List[Dict] = []

    def add_tx(
        tx_id: str,
        dt: datetime,
        sender: str,
        receiver: str,
        amount: float,
        tx_type: str,
        merch_cat: str,
        location: str,
        device_used: str,
        is_fraud: bool,
        fraud_type: str,
        spend_dev: float,
        velocity: int,
        geo_anom: float,
        channel: str,
        ip: str,
        dev_hash: str,
        scenario_tag: str,
    ) -> None:
        rows.append(
            {
                "transaction_id": tx_id,
                "timestamp": dt.isoformat(),
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": round(float(amount), 2),
                "transaction_type": tx_type,
                "merchant_category": merch_cat,
                "location": location,
                "device_used": device_used,
                "is_fraud": is_fraud,
                "fraud_type": fraud_type,
                "time_since_last_transaction": 12.0,
                "spending_deviation_score": spend_dev,
                "velocity_score": velocity,
                "geo_anomaly_score": geo_anom,
                "payment_channel": channel,
                "ip_address": ip,
                "device_hash": dev_hash,
                "is_synthetic": True,
                "data_source": "synthetic_typology",
                "scenario_tag": scenario_tag,
            }
        )

    # =========================================================================
    # SCENARIO 1: Multi-Hop Money Mule Chain & Rapid Pass-Through (Layering)
    # 5 Smurf Feeders -> ACC_MULE_7701 -> ACC_RELAY_7702 -> ACC_RELAY_7703 -> ACC_EXIT_7704
    # Plus covert shared device DEV_SHADOW_901 between ACC_MULE_7701 & ACC_RELAY_7703
    # =========================================================================
    smurf_feeders = [
        ("ACC_FEED_7101", 4650.00, 0, "103.44.19.11", "DEV_SMURF_01", "Singapore"),
        ("ACC_FEED_7102", 4820.00, 9, "103.44.19.48", "DEV_SMURF_02", "London"),
        ("ACC_FEED_7103", 4790.00, 17, "89.187.162.14", "DEV_SMURF_03", "Berlin"),
        ("ACC_FEED_7104", 4910.00, 24, "89.187.162.99", "DEV_SMURF_04", "Dubai"),
        ("ACC_FEED_7105", 4580.00, 31, "103.44.19.11", "DEV_SMURF_05", "Singapore"),
    ]
    for idx, (sender, amt, mins, ip, dev, loc) in enumerate(smurf_feeders, start=1):
        add_tx(
            f"SYN_MULE_10{idx}",
            base_time + timedelta(minutes=mins),
            sender,
            "ACC_MULE_7701",
            amt,
            "transfer",
            "financial_services",
            loc,
            "mobile",
            True,
            "mule_collection",
            3.4,
            9,
            0.84,
            "wire",
            ip,
            dev,
            "SCEN-01-MULE-LAYERING",
        )

    # Rapid multi-hop pass-through peeling ~2% fee at each hop within 15-25 mins
    # Total collected = 23,750.00
    t_hop1 = base_time + timedelta(minutes=46)
    add_tx(
        "SYN_MULE_201",
        t_hop1,
        "ACC_MULE_7701",
        "ACC_RELAY_7702",
        23250.00,
        "transfer",
        "financial_services",
        "Dubai",
        "mobile",
        True,
        "layering_passthrough",
        4.6,
        10,
        0.91,
        "wire",
        "185.220.101.33",
        "DEV_SHADOW_901",
        "SCEN-01-MULE-LAYERING",
    )
    t_hop2 = t_hop1 + timedelta(minutes=18)
    add_tx(
        "SYN_MULE_202",
        t_hop2,
        "ACC_RELAY_7702",
        "ACC_RELAY_7703",
        22790.00,
        "transfer",
        "crypto_exchange",
        "Zurich",
        "web",
        True,
        "layering_passthrough",
        4.3,
        9,
        0.88,
        "wire",
        "185.220.101.33",
        "DEV_RELAY_802",
        "SCEN-01-MULE-LAYERING",
    )
    t_hop3 = t_hop2 + timedelta(minutes=21)
    add_tx(
        "SYN_MULE_203",
        t_hop3,
        "ACC_RELAY_7703",
        "ACC_EXIT_7704",
        22340.00,
        "transfer",
        "crypto_exchange",
        "Hong Kong",
        "mobile",
        True,
        "layering_cashout",
        4.8,
        10,
        0.95,
        "wire",
        "185.220.101.90",
        "DEV_SHADOW_901",  # Same device as ACC_MULE_7701!
        "SCEN-01-MULE-LAYERING",
    )

    # =========================================================================
    # SCENARIO 2: High-Velocity Aggregator Hub (Fan-In + Fan-Out Distribution)
    # 6 feeders -> ACC_HUB_4400 -> 5 payout beneficiaries
    # =========================================================================
    t_s2 = base_time + timedelta(hours=3)
    for idx in range(1, 7):
        add_tx(
            f"SYN_HUB_30{idx}",
            t_s2 + timedelta(minutes=idx * 11),
            f"ACC_SRC_410{idx}",
            "ACC_HUB_4400",
            3600.0 + idx * 185.0,
            "transfer",
            "online_marketplace",
            "New York",
            "web",
            True,
            "fan_in_structuring",
            2.9,
            8,
            0.72,
            "ACH",
            f"198.51.100.{40 + idx}",
            f"DEV_SRC_41{idx}",
            "SCEN-02-AGGREGATOR-HUB",
        )

    for idx in range(1, 6):
        add_tx(
            f"SYN_HUB_40{idx}",
            t_s2 + timedelta(minutes=85 + idx * 8),
            "ACC_HUB_4400",
            f"ACC_OUT_490{idx}",
            4620.0 + idx * 75.0,
            "transfer",
            "remittance",
            "Miami",
            "web",
            True,
            "fan_out_dispersion",
            3.7,
            9,
            0.79,
            "wire",
            "198.51.100.77",
            "DEV_HUB_4400",
            "SCEN-02-AGGREGATOR-HUB",
        )

    # =========================================================================
    # SCENARIO 3: Circular Wash / Round-Tripping Ring (4-Account Cycle)
    # ACC_RING_301 -> ACC_RING_302 -> ACC_RING_303 -> ACC_RING_304 -> ACC_RING_301
    # =========================================================================
    t_s3 = base_time + timedelta(hours=6)
    cycle_hops = [
        ("SYN_CYC_501", "ACC_RING_301", "ACC_RING_302", 34500.00, 0, "London", "DEV_CYC_01"),
        ("SYN_CYC_502", "ACC_RING_302", "ACC_RING_303", 34120.00, 42, "Amsterdam", "DEV_CYC_02"),
        ("SYN_CYC_503", "ACC_RING_303", "ACC_RING_304", 33840.00, 95, "Luxembourg", "DEV_CYC_01"),
        ("SYN_CYC_504", "ACC_RING_304", "ACC_RING_301", 33590.00, 140, "London", "DEV_CYC_03"),
    ]
    for tx_id, src, dst, amt, mins, loc, dev in cycle_hops:
        add_tx(
            tx_id,
            t_s3 + timedelta(minutes=mins),
            src,
            dst,
            amt,
            "transfer",
            "consulting_b2b",
            loc,
            "web",
            True,
            "circular_round_trip",
            4.1,
            8,
            0.83,
            "wire",
            "185.220.101.52",  # Shared anonymizing proxy IP across ring
            dev,
            "SCEN-03-CIRCULAR-RING",
        )

    # =========================================================================
    # SCENARIO 4: Coordinated Device Emulator & Proxy Farm
    # 4 seemingly distinct accounts operating on identical device hash DEV_EMU_X88
    # =========================================================================
    t_s4 = base_time + timedelta(hours=10)
    for idx in range(1, 5):
        add_tx(
            f"SYN_FARM_60{idx}",
            t_s4 + timedelta(minutes=idx * 6),
            f"ACC_FARM_60{idx}",
            "ACC_CASHOUT_699",
            2890.0 + idx * 110.0,
            "transfer",
            "gaming_digital",
            "Toronto",
            "mobile",
            True,
            "device_farm_takeover",
            3.5,
            9,
            0.89,
            "UPI",
            "198.51.100.214",
            "DEV_EMU_X88",
            "SCEN-04-DEVICE-FARM",
        )

    # =========================================================================
    # SCENARIO 5: BENIGN CONTROL — Corporate Office NAT Shared IP (False-Positive Control)
    # 4 legitimate business accounts sharing office NAT IP 203.0.113.10 during normal
    # business hours with normal utility/vendor payments and unique devices.
    # =========================================================================
    t_s5 = base_time + timedelta(hours=1, minutes=30)
    for idx in range(1, 5):
        add_tx(
            f"SYN_CORP_70{idx}",
            t_s5 + timedelta(minutes=idx * 45),
            f"ACC_CORP_10{idx}",
            f"ACC_VENDOR_20{idx}",
            640.0 + idx * 85.0,
            "payment",
            "utilities",
            "Chicago",
            "web",
            False,
            "",
            0.12,
            2,
            0.08,
            "ACH",
            "203.0.113.10",  # Shared corporate office NAT IP
            f"DEV_CORP_LAPTOP_{idx}",
            "SCEN-05-BENIGN-CORP-NAT",
        )

    return pd.DataFrame(rows)

