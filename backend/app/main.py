"""
TRACE — Financial Crime Network Investigator FastAPI Application.
Modular monolith serving real graph analytics, pattern detections, Isolation Forest
anomaly scoring, evidence-grounded AI investigations, and case audit workflows.
"""
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.core.state import workspace_state
from app.graph_engine.builder import strip_prefix
from app.schemas.models import (
    CaseCreateRequest,
    CaseUpdateRequest,
    DatasetProcessRequest,
    InvestigationCreateRequest,
    NoteCreateRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    workspace_state.initialize()
    yield


app = FastAPI(
    title="TRACE — AI Financial Crime Network Investigator API",
    version="1.0.0",
    description=(
        "Network-centric financial crime relationship discovery, graph typology detection, "
        "unsupervised Isolation Forest anomaly scoring, and competing-hypothesis investigation engine."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# 1. HEALTH, METADATA & COMMAND CENTRE OVERVIEW
# -----------------------------------------------------------------------------
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy" if workspace_state.is_ready else "initializing",
        "service": "trace-financial-crime-investigator",
        "active_transactions": int(len(workspace_state.graph_engine.df)),
        "active_detections": len(workspace_state.detections),
        "ai_engine": workspace_state.investigator.get_ai_status(),
    }


@app.get("/api/overview")
def get_command_centre_overview() -> Dict[str, Any]:
    g = workspace_state.graph_engine
    df = g.df
    g_sum = g.get_graph_summary()

    risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    suspicious_accounts = []
    for aid, r in g.entity_risk.items():
        prio = r.get("priority", "LOW")
        risk_counts[prio] = risk_counts.get(prio, 0) + 1
        if prio in ("CRITICAL", "HIGH"):
            st = g.account_stats.get(aid, {})
            suspicious_accounts.append(
                {
                    "entity_id": aid,
                    "label": st.get("label", strip_prefix(aid)),
                    "risk_score": r["risk_score"],
                    "priority": prio,
                    "pattern_types": r["pattern_types"],
                    "total_volume": st.get("total_volume", 0.0),
                    "total_tx_count": st.get("total_tx_count", 0),
                    "is_synthetic": bool(st.get("is_synthetic", False)),
                }
            )
    suspicious_accounts.sort(key=lambda x: x["risk_score"], reverse=True)

    # Pattern distribution
    pattern_breakdown: Dict[str, int] = {}
    for det in workspace_state.detections:
        pattern_breakdown[det.pattern_type] = pattern_breakdown.get(det.pattern_type, 0) + 1

    # Temporal volume & anomaly trend (bucketed by date/period)
    timeline_series: List[Dict[str, Any]] = []
    if not df.empty:
        temp = df[["timestamp", "amount", "ml_is_anomaly", "is_synthetic"]].copy()
        temp["day"] = temp["timestamp"].str.slice(0, 10)
        grouped = (
            temp.groupby("day", as_index=False)
            .agg(
                tx_count=("amount", "count"),
                volume=("amount", "sum"),
                anomalies=("ml_is_anomaly", "sum"),
            )
            .sort_values("day")
        )
        if len(grouped) > 24:
            grouped = grouped.tail(24)
        for row in grouped.to_dict(orient="records"):
            timeline_series.append(
                {
                    "period": row["day"],
                    "tx_count": int(row["tx_count"]),
                    "volume": round(float(row["volume"]), 2),
                    "anomalies": int(row["anomalies"]),
                }
            )

    return {
        "kpis": {
            **g_sum,
            "suspicious_entities_review": risk_counts["CRITICAL"] + risk_counts["HIGH"],
            "critical_entities": risk_counts["CRITICAL"],
            "total_detections": len(workspace_state.detections),
            "ml_anomalous_transactions": int(
                df["ml_is_anomaly"].sum() if "ml_is_anomaly" in df.columns else 0
            ),
            "open_cases": len([c for c in workspace_state.db.list_cases() if c["status"] != "CLOSED_BENIGN"]),
        },
        "risk_distribution": [
            {"priority": k, "count": v} for k, v in risk_counts.items()
        ],
        "pattern_breakdown": [
            {"pattern_type": k, "count": v} for k, v in pattern_breakdown.items()
        ],
        "activity_timeline": timeline_series,
        "top_suspicious_entities": suspicious_accounts[:12],
        "top_detections": [d.model_dump() for d in workspace_state.detections[:10]],
        "recent_cases": workspace_state.db.list_cases()[:6],
        "dataset_quality": workspace_state.quality_report,
        "ai_status": workspace_state.investigator.get_ai_status(),
    }


# -----------------------------------------------------------------------------
# 2. DATASET & MODEL HEALTH ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/api/datasets/status")
def get_dataset_status() -> Dict[str, Any]:
    return {
        "ready": workspace_state.is_ready,
        "quality_report": workspace_state.quality_report,
        "graph_summary": workspace_state.graph_engine.get_graph_summary(),
    }


@app.post("/api/datasets/process")
def reprocess_dataset(req: DatasetProcessRequest) -> Dict[str, Any]:
    quality = workspace_state.reprocess_dataset(
        source_mode=req.source_mode,
        max_kaggle_rows=req.max_kaggle_rows,
        include_synthetic_scenarios=req.include_synthetic_scenarios,
    )
    return {
        "status": "processed",
        "quality_report": quality,
        "detections_found": len(workspace_state.detections),
        "graph_summary": workspace_state.graph_engine.get_graph_summary(),
    }


@app.post("/api/datasets/upload")
async def upload_csv_dataset(
    file: UploadFile = File(...),
    include_synthetic_scenarios: bool = Form(False),
    max_rows: int = Form(25000),
) -> Dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a valid .csv transaction file.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")
    try:
        quality = workspace_state.process_uploaded_csv(
            filename=file.filename,
            content=content,
            include_synthetic_scenarios=include_synthetic_scenarios,
            max_rows=max_rows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "uploaded_and_processed",
        "quality_report": quality,
        "detections_found": len(workspace_state.detections),
        "graph_summary": workspace_state.graph_engine.get_graph_summary(),
    }


@app.get("/api/models/status")
def get_models_status() -> Dict[str, Any]:
    return {
        "isolation_forest": workspace_state.ml_engine.model_metadata,
        "graph_engine": workspace_state.graph_engine.get_graph_summary(),
        "ai_investigator": workspace_state.investigator.get_ai_status(),
    }


# -----------------------------------------------------------------------------
# 3. NETWORK INTELLIGENCE GRAPH ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/api/graph/subgraph")
def get_investigation_subgraph(
    pattern_type: Optional[str] = Query(None),
    min_risk: float = Query(0.0, ge=0.0, le=100.0),
    include_devices: bool = Query(True),
    include_ips: bool = Query(True),
    data_source_filter: str = Query("all"),  # all | real_only | synthetic_only
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    max_nodes: int = Query(130, ge=15, le=350),
) -> Dict[str, Any]:
    g = workspace_state.graph_engine

    if search and search.strip():
        q = search.strip()
        resolved = g.resolve_entity_id(q)
        if resolved:
            return g.get_ego_subgraph(resolved, hops=2, max_nodes=max_nodes)
        # Substring match across entities
        matched = {
            nid
            for nid, nd in g.hetero_graph.nodes(data=True)
            if q.lower() in str(nd.get("label", "")).lower() or q.lower() in nid.lower()
        }
        if matched:
            expanded = set(matched)
            for m in list(matched)[:15]:
                expanded.update(g.hetero_graph.predecessors(m))
                expanded.update(g.hetero_graph.successors(m))
            return g.serialize_subgraph(expanded, max_nodes=max_nodes)

    seed_nodes: Set[str] = set()
    # Start from detected suspicious networks so default graph view immediately shows rich multi-hop structures!
    for det in workspace_state.detections:
        if pattern_type and det.pattern_type != pattern_type:
            continue
        if data_source_filter == "real_only" and det.is_synthetic_scenario:
            continue
        if data_source_filter == "synthetic_only" and not det.is_synthetic_scenario:
            continue
        seed_nodes.update(det.involved_entities)

    # Supplement with top-degree/connected real accounts so graph has organic context
    if len(seed_nodes) < max_nodes:
        candidates = sorted(
            g.account_stats.keys(),
            key=lambda aid: (
                g.entity_risk.get(aid, {}).get("risk_score", 0.0),
                g.account_stats[aid]["total_tx_count"],
            ),
            reverse=True,
        )
        for aid in candidates:
            is_syn = g.account_stats[aid].get("is_synthetic", False)
            if data_source_filter == "real_only" and is_syn:
                continue
            if data_source_filter == "synthetic_only" and not is_syn:
                continue
            seed_nodes.add(aid)
            if len(seed_nodes) >= max_nodes:
                break

    allowed_types = {"ACCOUNT"}
    if include_devices:
        allowed_types.add("DEVICE")
    if include_ips:
        allowed_types.add("IP_ADDRESS")

    return g.serialize_subgraph(
        seed_nodes=seed_nodes,
        include_shared_infra=(include_devices or include_ips),
        entity_types=allowed_types,
        min_risk=min_risk,
        start_ts=start_date,
        end_ts=end_date,
        max_nodes=max_nodes,
    )


@app.get("/api/graph/ego/{entity_id:path}")
def get_entity_ego_graph(
    entity_id: str,
    hops: int = Query(2, ge=1, le=4),
    max_nodes: int = Query(120, ge=10, le=280),
) -> Dict[str, Any]:
    res = workspace_state.graph_engine.get_ego_subgraph(entity_id, hops=hops, max_nodes=max_nodes)
    if not res["nodes"]:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in graph.")
    return res


@app.get("/api/graph/paths")
def get_paths_between_entities(
    source: str = Query(...),
    target: str = Query(...),
    max_hops: int = Query(5, ge=1, le=7),
) -> Dict[str, Any]:
    return workspace_state.graph_engine.find_connecting_paths(source, target, max_hops=max_hops)


# -----------------------------------------------------------------------------
# 4. ENTITIES & TRANSACTIONS ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/api/entities")
def list_entities(
    search: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    pattern_type: Optional[str] = Query(None),
    data_source_filter: str = Query("all"),
    limit: int = Query(60, ge=1, le=250),
) -> Dict[str, Any]:
    g = workspace_state.graph_engine
    items = []
    for aid, st in g.account_stats.items():
        r = g.entity_risk.get(aid, {})
        if priority and r.get("priority") != priority:
            continue
        if pattern_type and pattern_type not in r.get("pattern_types", []):
            continue
        if data_source_filter == "real_only" and st.get("is_synthetic"):
            continue
        if data_source_filter == "synthetic_only" and not st.get("is_synthetic"):
            continue
        if search and search.lower() not in aid.lower() and search.lower() not in st["label"].lower():
            continue
        items.append(
            {
                "entity_id": aid,
                "label": st["label"],
                "entity_type": "ACCOUNT",
                "risk_score": r.get("risk_score", 0.0),
                "priority": r.get("priority", "LOW"),
                "ml_anomaly_score": r.get("ml_anomaly_score", 0.0),
                "pattern_types": r.get("pattern_types", []),
                "in_count": st["in_count"],
                "out_count": st["out_count"],
                "total_volume": st["total_volume"],
                "is_synthetic": st["is_synthetic"],
                "locations": st["locations"],
            }
        )

    items.sort(key=lambda x: (x["risk_score"], x["total_volume"]), reverse=True)
    return {"total": len(items), "items": items[:limit]}


@app.get("/api/entities/{entity_id:path}")
def get_entity_details(entity_id: str) -> Dict[str, Any]:
    detail = workspace_state.graph_engine.get_entity_detail(entity_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found.")
    det_ids = set(detail.get("detection_ids", []))
    detail["detections"] = [
        d.model_dump() for d in workspace_state.detections if d.detection_id in det_ids
    ]
    return detail


@app.get("/api/transactions")
def list_transactions(
    search: Optional[str] = Query(None),
    account: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    anomalies_only: bool = Query(False),
    data_source_filter: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=10, le=200),
) -> Dict[str, Any]:
    df = workspace_state.graph_engine.df
    if df.empty:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    sub = df
    if search:
        q = search.strip().lower()
        sub = sub[
            sub["transaction_id"].str.lower().str.contains(q, na=False)
            | sub["sender_account"].str.lower().str.contains(q, na=False)
            | sub["receiver_account"].str.lower().str.contains(q, na=False)
            | sub["ip_address"].str.lower().str.contains(q, na=False)
            | sub["device_hash"].str.lower().str.contains(q, na=False)
        ]
    if account:
        raw_acc = strip_prefix(account.strip())
        sub = sub[(sub["sender_account"] == raw_acc) | (sub["receiver_account"] == raw_acc)]
    if transaction_type:
        sub = sub[sub["transaction_type"] == transaction_type]
    if min_amount is not None:
        sub = sub[sub["amount"] >= min_amount]
    if max_amount is not None:
        sub = sub[sub["amount"] <= max_amount]
    if anomalies_only:
        sub = sub[sub["ml_is_anomaly"] | sub["is_fraud"]]
    if data_source_filter == "real_only":
        sub = sub[~sub["is_synthetic"]]
    elif data_source_filter == "synthetic_only":
        sub = sub[sub["is_synthetic"]]

    sub = sub.sort_values(["ml_anomaly_score", "amount"], ascending=[False, False])
    total = int(len(sub))
    start = (page - 1) * page_size
    page_df = sub.iloc[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_df.to_dict(orient="records"),
    }


@app.get("/api/transactions/{transaction_id}")
def get_transaction_detail(transaction_id: str) -> Dict[str, Any]:
    tx = workspace_state.graph_engine.tx_lookup.get(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")
    s_id = f"ACCOUNT:{tx['sender_account']}"
    r_id = f"ACCOUNT:{tx['receiver_account']}"
    related_dets = [
        d.model_dump()
        for d in workspace_state.detections
        if transaction_id in d.supporting_transactions
        or s_id in d.involved_entities
        or r_id in d.involved_entities
    ]
    return {
        "transaction": tx,
        "sender_risk": workspace_state.graph_engine.entity_risk.get(s_id, {}),
        "receiver_risk": workspace_state.graph_engine.entity_risk.get(r_id, {}),
        "related_detections": related_dets[:8],
    }


# -----------------------------------------------------------------------------
# 5. PATTERN DETECTIONS ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/api/detections")
def list_detections(
    pattern_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    data_source_filter: str = Query("all"),
) -> Dict[str, Any]:
    items = workspace_state.detections
    if pattern_type:
        items = [d for d in items if d.pattern_type == pattern_type]
    if severity:
        items = [d for d in items if d.severity == severity]
    if data_source_filter == "real_only":
        items = [d for d in items if not d.is_synthetic_scenario]
    elif data_source_filter == "synthetic_only":
        items = [d for d in items if d.is_synthetic_scenario]

    return {
        "total": len(items),
        "items": [d.model_dump() for d in items],
    }


@app.get("/api/detections/{detection_id}")
def get_detection_by_id(detection_id: str) -> Dict[str, Any]:
    for d in workspace_state.detections:
        if d.detection_id == detection_id:
            subgraph = workspace_state.graph_engine.serialize_subgraph(
                set(d.involved_entities), include_shared_infra=True, max_nodes=80
            )
            txs = [
                workspace_state.graph_engine.tx_lookup[tid]
                for tid in d.supporting_transactions
                if tid in workspace_state.graph_engine.tx_lookup
            ]
            return {
                "detection": d.model_dump(),
                "subgraph": subgraph,
                "transactions": txs,
            }
    raise HTTPException(status_code=404, detail=f"Detection '{detection_id}' not found.")


# -----------------------------------------------------------------------------
# 6. AI INVESTIGATION WORKBENCH & CASES ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/api/investigations")
def run_investigation(req: InvestigationCreateRequest) -> Dict[str, Any]:
    try:
        report = workspace_state.investigator.investigate(
            target_id=req.target_id,
            target_type=req.target_type,
            graph_engine=workspace_state.graph_engine,
            detections=workspace_state.detections,
            use_llm_if_available=req.use_llm_if_available,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = report.model_dump()
    workspace_state.db.save_investigation(payload)
    return payload


@app.get("/api/investigations")
def list_investigations() -> Dict[str, Any]:
    items = workspace_state.db.list_investigations(limit=30)
    return {"total": len(items), "items": items}


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: str) -> Dict[str, Any]:
    item = workspace_state.db.get_investigation(investigation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Investigation report not found.")
    return item


@app.post("/api/investigations/{investigation_id}/notes")
def add_note_or_verdict(investigation_id: str, req: NoteCreateRequest) -> Dict[str, Any]:
    existing = workspace_state.db.get_investigation(investigation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Investigation report not found.")
    workspace_state.db.add_investigation_note(
        investigation_id=investigation_id,
        author=req.author,
        content=req.content,
        hypothesis_id=req.hypothesis_id,
        verdict=req.verdict,
    )
    return workspace_state.db.get_investigation(investigation_id)  # type: ignore


@app.get("/api/cases")
def list_cases() -> Dict[str, Any]:
    cases = workspace_state.db.list_cases()
    return {"total": len(cases), "items": cases}


@app.post("/api/cases")
def create_case(req: CaseCreateRequest) -> Dict[str, Any]:
    return workspace_state.db.create_case(
        title=req.title,
        primary_entity=req.primary_entity,
        priority=req.priority,
        assigned_analyst=req.assigned_analyst,
        investigation_id=req.investigation_id,
        detection_ids=req.detection_ids,
        summary=req.summary,
    )


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> Dict[str, Any]:
    c = workspace_state.db.get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    return c


@app.patch("/api/cases/{case_id}")
def update_case(case_id: str, req: CaseUpdateRequest) -> Dict[str, Any]:
    updated = workspace_state.db.update_case(
        case_id=case_id,
        status=req.status,
        priority=req.priority,
        assigned_analyst=req.assigned_analyst,
        note=req.note,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found.")
    return updated

