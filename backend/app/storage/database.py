"""
SQLite Persistence Layer for Investigations, Cases, Analyst Notes, Audit Logs,
and Dataset Ingestion Runs.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import SQLITE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InvestigationDatabase:
    def __init__(self, db_path=SQLITE_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    overall_priority TEXT NOT NULL,
                    composite_risk_score REAL NOT NULL,
                    generation_mode TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS investigation_notes (
                    note_id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    content TEXT NOT NULL,
                    hypothesis_id TEXT,
                    verdict TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    primary_entity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    assigned_analyst TEXT NOT NULL,
                    investigation_id TEXT,
                    detection_ids_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS case_timeline (
                    event_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_runs (
                    run_id TEXT PRIMARY KEY,
                    source_description TEXT NOT NULL,
                    active_rows INTEGER NOT NULL,
                    quarantined_rows INTEGER NOT NULL,
                    quality_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def record_dataset_run(self, quality_report: Dict[str, Any]) -> None:
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dataset_runs (run_id, source_description, active_rows, quarantined_rows, quality_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    quality_report.get("source_description", "Unknown"),
                    int(quality_report.get("active_rows_loaded", 0)),
                    int(quality_report.get("quarantined_rows", 0)),
                    json.dumps(quality_report),
                    _utc_now(),
                ),
            )

    def get_latest_dataset_run(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT quality_json FROM dataset_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return json.loads(row["quality_json"]) if row else None

    def save_investigation(self, report_dict: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO investigations
                (investigation_id, target_id, target_type, created_at, overall_priority, composite_risk_score, generation_mode, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_dict["investigation_id"],
                    report_dict["target_id"],
                    report_dict["target_type"],
                    report_dict["created_at"],
                    report_dict["overall_priority"],
                    float(report_dict["composite_risk_score"]),
                    report_dict["generation_mode"],
                    json.dumps(report_dict),
                ),
            )

    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM investigations WHERE investigation_id = ?",
                (investigation_id,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload_json"])
            notes = conn.execute(
                "SELECT * FROM investigation_notes WHERE investigation_id = ? ORDER BY created_at ASC",
                (investigation_id,),
            ).fetchall()
            payload["notes"] = [dict(n) for n in notes]
            return payload

    def list_investigations(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT investigation_id, target_id, target_type, created_at, overall_priority, composite_risk_score, generation_mode
                FROM investigations ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def add_investigation_note(
        self,
        investigation_id: str,
        author: str,
        content: str,
        hypothesis_id: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> Dict[str, Any]:
        note_id = f"NOTE-{uuid.uuid4().hex[:8].upper()}"
        created_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO investigation_notes (note_id, investigation_id, author, content, hypothesis_id, verdict, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (note_id, investigation_id, author, content, hypothesis_id, verdict, created_at),
            )
            if hypothesis_id and verdict:
                row = conn.execute(
                    "SELECT payload_json FROM investigations WHERE investigation_id = ?",
                    (investigation_id,),
                ).fetchone()
                if row:
                    payload = json.loads(row["payload_json"])
                    for hyp in payload.get("hypotheses", []):
                        if hyp.get("hypothesis_id") == hypothesis_id:
                            hyp["analyst_verdict"] = verdict
                    conn.execute(
                        "UPDATE investigations SET payload_json = ? WHERE investigation_id = ?",
                        (json.dumps(payload), investigation_id),
                    )
        return {
            "note_id": note_id,
            "investigation_id": investigation_id,
            "author": author,
            "content": content,
            "hypothesis_id": hypothesis_id,
            "verdict": verdict,
            "created_at": created_at,
        }

    def create_case(
        self,
        title: str,
        primary_entity: str,
        priority: str,
        assigned_analyst: str,
        investigation_id: Optional[str],
        detection_ids: List[str],
        summary: str,
    ) -> Dict[str, Any]:
        case_id = f"CASE-{uuid.uuid4().hex[:6].upper()}"
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cases
                (case_id, title, primary_entity, status, priority, assigned_analyst, investigation_id, detection_ids_json, summary, created_at, updated_at)
                VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    title,
                    primary_entity,
                    priority,
                    assigned_analyst,
                    investigation_id,
                    json.dumps(detection_ids),
                    summary,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO case_timeline (event_id, case_id, actor, action, detail, created_at)
                VALUES (?, ?, ?, 'CASE_CREATED', ?, ?)
                """,
                (
                    f"EVT-{uuid.uuid4().hex[:8].upper()}",
                    case_id,
                    assigned_analyst,
                    f"Opened investigation case for {primary_entity} (Priority: {priority}).",
                    now,
                ),
            )
        return self.get_case(case_id)  # type: ignore

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["detection_ids"] = json.loads(item.pop("detection_ids_json", "[]"))
            events = conn.execute(
                "SELECT * FROM case_timeline WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,),
            ).fetchall()
            item["timeline"] = [dict(e) for e in events]
            return item

    def list_cases(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["detection_ids"] = json.loads(item.pop("detection_ids_json", "[]"))
                results.append(item)
            return results

    def update_case(
        self,
        case_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_analyst: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_case(case_id)
        if not existing:
            return None
        now = _utc_now()
        new_status = status or existing["status"]
        new_priority = priority or existing["priority"]
        new_analyst = assigned_analyst or existing["assigned_analyst"]

        changes = []
        if status and status != existing["status"]:
            changes.append(f"Status changed {existing['status']} -> {status}")
        if priority and priority != existing["priority"]:
            changes.append(f"Priority changed {existing['priority']} -> {priority}")
        if assigned_analyst and assigned_analyst != existing["assigned_analyst"]:
            changes.append(f"Reassigned to {assigned_analyst}")
        if note:
            changes.append(f"Analyst note: {note}")

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE cases SET status = ?, priority = ?, assigned_analyst = ?, updated_at = ?
                WHERE case_id = ?
                """,
                (new_status, new_priority, new_analyst, now, case_id),
            )
            if changes:
                conn.execute(
                    """
                    INSERT INTO case_timeline (event_id, case_id, actor, action, detail, created_at)
                    VALUES (?, ?, ?, 'CASE_UPDATED', ?, ?)
                    """,
                    (
                        f"EVT-{uuid.uuid4().hex[:8].upper()}",
                        case_id,
                        new_analyst,
                        " | ".join(changes),
                        now,
                    ),
                )
        return self.get_case(case_id)

