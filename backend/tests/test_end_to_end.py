"""
End-to-End Verification Suite for TRACE Financial Crime Network Investigator.
Tests:
  1. Dataset ingestion, validation, quarantine, and real-vs-synthetic provenance.
  2. NetworkX heterogeneous & directed multi-edge graph construction and path queries.
  3. All required financial-crime pattern detectors (including verifying detection of the
     known multi-hop money mule chain and low-risk handling of benign corporate NAT).
  4. Isolation Forest behavioral anomaly detection & hybrid risk contributions.
  5. FastAPI REST endpoints (overview, subgraph, ego-graph, CSV upload, AI investigation, cases).
"""
import pandas as pd
import pytest

from app.core.state import workspace_state
from app.ingestion.pipeline import _clean_and_validate_chunk
from app.main import (
    add_note_or_verdict,
    create_case,
    get_command_centre_overview,
    get_entity_ego_graph,
    get_health,
    get_investigation_subgraph,
    list_transactions,
    reprocess_dataset,
    run_investigation,
    update_case,
)
from app.schemas.models import (
    CaseCreateRequest,
    CaseUpdateRequest,
    DatasetProcessRequest,
    InvestigationCreateRequest,
    NoteCreateRequest,
)


@pytest.fixture(scope="module", autouse=True)
def initialized_workspace():
    workspace_state.initialize()
    return workspace_state


def test_dataset_ingestion_and_quarantine():
    raw = pd.DataFrame(
        [
            {
                "transaction_id": "TX_VALID_1",
                "timestamp": "2023-10-01T10:00:00",
                "sender_account": "A1",
                "receiver_account": "A2",
                "amount": 500.0,
            },
            {
                "transaction_id": "TX_VALID_1",  # duplicate ID -> quarantine
                "timestamp": "2023-10-01T10:05:00",
                "sender_account": "A1",
                "receiver_account": "A3",
                "amount": 300.0,
            },
            {
                "transaction_id": "TX_NEG_AMT",  # negative amount -> quarantine
                "timestamp": "2023-10-01T10:10:00",
                "sender_account": "A2",
                "receiver_account": "A3",
                "amount": -45.0,
            },
            {
                "transaction_id": "TX_SELF",  # self loop -> quarantine
                "timestamp": "2023-10-01T10:15:00",
                "sender_account": "A9",
                "receiver_account": "A9",
                "amount": 100.0,
            },
        ]
    )
    valid, quarantined, stats = _clean_and_validate_chunk(raw, set())
    assert len(valid) == 1
    assert len(quarantined) == 3
    assert stats["duplicate_tx_id"] == 1
    assert stats["invalid_amount"] == 1
    assert stats["self_loop"] == 1


def test_graph_construction_and_mule_path_discovery(initialized_workspace):
    g = initialized_workspace.graph_engine
    summary = g.get_graph_summary()
    assert summary["total_transactions"] > 50
    assert summary["unique_accounts"] > 20
    assert summary["shared_devices_count"] >= 2

    # Verify multi-hop directed path from smurf feeder through mule layering relays to exit account
    paths = g.find_connecting_paths("ACC_FEED_7101", "ACC_EXIT_7704", max_hops=6)
    assert len(paths["directed_paths"]) >= 1
    chain = paths["directed_paths"][0]
    assert chain == [
        "ACCOUNT:ACC_FEED_7101",
        "ACCOUNT:ACC_MULE_7701",
        "ACCOUNT:ACC_RELAY_7702",
        "ACCOUNT:ACC_RELAY_7703",
        "ACCOUNT:ACC_EXIT_7704",
    ]


def test_known_money_mule_chain_and_all_core_patterns_detected(initialized_workspace):
    dets = initialized_workspace.detections
    by_type = {}
    for d in dets:
        by_type.setdefault(d.pattern_type, []).append(d)

    # All core pattern detectors must fire
    for required_type in [
        "FAN_IN",
        "FAN_OUT",
        "RAPID_PASS_THROUGH",
        "CIRCULAR_FLOW",
        "SHARED_DEVICE",
        "SHARED_IP",
        "MULE_ACCOUNT_INDICATOR",
    ]:
        assert required_type in by_type, f"Expected pattern {required_type} to be detected"

    # Verify known money mule chain (ACC_MULE_7701 -> ACC_RELAY_7702 -> ACC_RELAY_7703) is detected
    layer_entities = {
        ent for d in by_type["RAPID_PASS_THROUGH"] for ent in d.involved_entities
    }
    assert "ACCOUNT:ACC_MULE_7701" in layer_entities
    assert "ACCOUNT:ACC_RELAY_7702" in layer_entities
    assert "ACCOUNT:ACC_RELAY_7703" in layer_entities

    # Verify circular wash ring (ACC_RING_301..304) is detected
    cycle_entities = {ent for d in by_type["CIRCULAR_FLOW"] for ent in d.involved_entities}
    assert "ACCOUNT:ACC_RING_301" in cycle_entities
    assert "ACCOUNT:ACC_RING_303" in cycle_entities

    # Verify benign corporate office NAT (203.0.113.10) is conservatively scored LOW severity
    corp_nat_dets = [
        d for d in by_type["SHARED_IP"] if d.primary_entity == "IP:203.0.113.10"
    ]
    assert len(corp_nat_dets) == 1
    assert corp_nat_dets[0].severity == "LOW"
    assert corp_nat_dets[0].metrics["benign_nat_likeness"] is True


def test_isolation_forest_and_hybrid_risk_scores(initialized_workspace):
    meta = initialized_workspace.ml_engine.model_metadata
    assert meta["anomalous_transactions_flagged"] > 0
    assert len(meta["features"]) == 10

    mule_risk = initialized_workspace.graph_engine.entity_risk.get("ACCOUNT:ACC_MULE_7701")
    assert mule_risk is not None
    assert mule_risk["priority"] in ("CRITICAL", "HIGH")
    assert len(mule_risk["contributions"]) == 4


def test_fastapi_endpoints_and_investigation_workflow(initialized_workspace):
    h = get_health()
    assert h["status"] == "healthy"

    ov = get_command_centre_overview()
    assert ov["kpis"]["total_detections"] > 0

    sg = get_investigation_subgraph(
        pattern_type=None,
        min_risk=0.0,
        include_devices=True,
        include_ips=True,
        data_source_filter="all",
        search=None,
        start_date=None,
        end_date=None,
        max_nodes=60,
    )
    assert len(sg["nodes"]) > 5

    ego = get_entity_ego_graph("ACCOUNT:ACC_MULE_7701", hops=2, max_nodes=80)
    assert any(n["id"] == "ACCOUNT:ACC_MULE_7701" for n in ego["nodes"])

    txs = list_transactions(
        search=None,
        account=None,
        transaction_type=None,
        min_amount=None,
        max_amount=None,
        anomalies_only=True,
        data_source_filter="all",
        page=1,
        page_size=15,
    )
    assert len(txs["items"]) > 0

    # Generate Evidence-Grounded Investigation Report
    rep = run_investigation(
        InvestigationCreateRequest(
            target_id="ACCOUNT:ACC_MULE_7701",
            target_type="ACCOUNT",
            use_llm_if_available=False,
        )
    )
    assert rep["overall_priority"] == "CRITICAL"
    assert len(rep["verified_facts"]) >= 4
    categories = {hyp["category"] for hyp in rep["hypotheses"]}
    assert "SUSPICIOUS_TYPOLOGY" in categories
    assert "BENIGN_ALTERNATIVE" in categories

    # Record analyst verdict on hypothesis
    updated_rep = add_note_or_verdict(
        rep["investigation_id"],
        NoteCreateRequest(
            author="Test Analyst",
            content="Verified shared device correlation across hop 1 and hop 3.",
            hypothesis_id=rep["hypotheses"][0]["hypothesis_id"],
            verdict="USEFUL",
        ),
    )
    assert updated_rep["hypotheses"][0]["analyst_verdict"] == "USEFUL"

    # Case creation & status transition audit trail
    case = create_case(
        CaseCreateRequest(
            title="Test Mule Ring Escalation",
            primary_entity="ACCOUNT:ACC_MULE_7701",
            priority="CRITICAL",
            investigation_id=rep["investigation_id"],
            summary=rep["executive_summary"],
        )
    )
    moved = update_case(
        case["case_id"],
        CaseUpdateRequest(status="ESCALATED", note="Confirmed multi-hop pass-through."),
    )
    assert moved["status"] == "ESCALATED"
    assert len(moved["timeline"]) >= 2

    # Test CSV dataset upload pipeline & restore default hybrid dataset
    csv_bytes = (
        "transaction_id,timestamp,sender_account,receiver_account,amount,device_hash,ip_address\n"
        "UP_1,2023-12-01T10:00:00,U_A,U_B,4500,D_UP1,10.0.0.1\n"
        "UP_2,2023-12-01T10:15:00,U_B,U_C,4410,D_UP1,10.0.0.1\n"
        "UP_3,2023-12-01T10:25:00,U_C,U_A,4380,D_UP2,10.0.0.1\n"
    ).encode("utf-8")
    q_up = workspace_state.process_uploaded_csv(
        filename="mini_ring.csv",
        content=csv_bytes,
        include_synthetic_scenarios=True,
        max_rows=5000,
    )
    assert q_up["active_rows_loaded"] >= 3
    from app.core.config import RAW_DATA_DIR
    for p in RAW_DATA_DIR.glob("*mini_ring.csv"):
        p.unlink(missing_ok=True)

    restored = reprocess_dataset(
        DatasetProcessRequest(
            source_mode="hybrid",
            max_kaggle_rows=6000,
            include_synthetic_scenarios=True,
        )
    )
    assert restored["status"] == "processed"

