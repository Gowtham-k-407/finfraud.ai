"""
Evidence-Grounded Financial Crime Investigation Agent.
Executes a structured 6-step investigative workflow:
  1. Target Resolution (Account, Detection, or Transaction)
  2. Grounded Evidence Gathering (Direct Ledger Facts + Infrastructure Telemetry + Analytical Signals)
  3. Competing Hypothesis Generation (Suspicious Typologies vs. Benign Operational Explanations)
  4. Hypothesis Evaluation (Supporting, Contradicting & Missing Evidence + Confidence Basis)
  5. Structured Narrative Synthesis (LLM-grounded when API key configured; deterministic fallback otherwise)
  6. Human-in-the-Loop Case & Verdict Integration
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL
from app.graph_engine.builder import FinancialGraphEngine, strip_prefix
from app.schemas.models import (
    EvidenceItem,
    HypothesisEvaluation,
    InvestigationReport,
    PatternDetection,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceGroundedInvestigator:
    def __init__(self) -> None:
        self.has_gemini = bool(GEMINI_API_KEY)
        self.has_openai = bool(OPENAI_API_KEY)

    def get_ai_status(self) -> Dict[str, Any]:
        if self.has_gemini:
            return {
                "llm_configured": True,
                "provider": f"Google Gemini ({GEMINI_MODEL})",
                "fallback_ready": True,
            }
        if self.has_openai:
            return {
                "llm_configured": True,
                "provider": f"OpenAI Compatible ({OPENAI_MODEL})",
                "fallback_ready": True,
            }
        return {
            "llm_configured": False,
            "provider": "Deterministic Evidence-Grounded Reasoning Engine",
            "fallback_ready": True,
        }

    def investigate(
        self,
        target_id: str,
        target_type: str,
        graph_engine: FinancialGraphEngine,
        detections: List[PatternDetection],
        use_llm_if_available: bool = True,
    ) -> InvestigationReport:
        det_map = {d.detection_id: d for d in detections}
        focal_entity: Optional[str] = None
        focal_detection: Optional[PatternDetection] = None
        focal_tx: Optional[Dict[str, Any]] = None

        if target_type == "DETECTION" or target_id in det_map:
            focal_detection = det_map.get(target_id)
            if focal_detection:
                target_type = "DETECTION"
                focal_entity = focal_detection.primary_entity
        elif target_type == "TRANSACTION" or target_id in graph_engine.tx_lookup:
            focal_tx = graph_engine.tx_lookup.get(target_id)
            if focal_tx:
                target_type = "TRANSACTION"
                focal_entity = f"ACCOUNT:{focal_tx['sender_account']}"

        if not focal_entity:
            focal_entity = graph_engine.resolve_entity_id(target_id)
            target_type = "ACCOUNT"

        if not focal_entity or focal_entity not in graph_engine.hetero_graph:
            raise ValueError(f"Investigation target '{target_id}' was not found in active graph.")

        detail = graph_engine.get_entity_detail(focal_entity) or {}
        related_dets = [
            d
            for d in detections
            if focal_entity in d.involved_entities
            or (focal_detection and d.detection_id == focal_detection.detection_id)
        ]

        # Collect verified facts vs analytical inferences
        verified_facts: List[EvidenceItem] = []
        involved_entities_set = {focal_entity}
        supporting_tx_ids: List[str] = []
        suspicious_paths: List[List[str]] = []
        timestamps: List[str] = []

        # 1. Direct Transaction Ledger Facts
        recent_txs = detail.get("recent_transactions", [])
        if focal_tx and focal_tx not in recent_txs:
            recent_txs = [focal_tx] + recent_txs

        total_vol = 0.0
        has_synthetic = False
        has_real = False
        for idx, tx in enumerate(recent_txs[:10], start=1):
            tid = str(tx["transaction_id"])
            if tid not in supporting_tx_ids:
                supporting_tx_ids.append(tid)
            amt = float(tx["amount"])
            total_vol += amt
            ts = str(tx["timestamp"])
            timestamps.append(ts)
            s_acc = f"ACCOUNT:{tx['sender_account']}"
            r_acc = f"ACCOUNT:{tx['receiver_account']}"
            involved_entities_set.update([s_acc, r_acc])
            if tx.get("is_synthetic"):
                has_synthetic = True
            else:
                has_real = True

            verified_facts.append(
                EvidenceItem(
                    evidence_id=f"EV-TX-{idx:02d}",
                    category="FACT_TRANSACTION",
                    title=f"Ledger Transfer {tid} (${amt:,.2f})",
                    description=(
                        f"Direct transfer of ${amt:,.2f} from {tx['sender_account']} to "
                        f"{tx['receiver_account']} via {tx.get('payment_channel', 'wire')} at {ts} "
                        f"[source: {tx.get('data_source', 'kaggle_real')}]."
                    ),
                    is_direct_fact=True,
                    confidence="HIGH",
                    related_entities=[s_acc, r_acc],
                    supporting_transactions=[tid],
                    timestamp=ts,
                    amount=amt,
                    metadata={
                        "velocity_score": tx.get("velocity_score"),
                        "ml_anomaly_score": tx.get("ml_anomaly_score", 0.0),
                        "is_synthetic": bool(tx.get("is_synthetic", False)),
                    },
                )
            )

        # 2. Direct Infrastructure Telemetry Facts (Shared Devices / IPs)
        infra_idx = 0
        for dev in detail.get("devices", []):
            if dev.get("is_shared"):
                infra_idx += 1
                co_accts = dev.get("co_using_accounts", [])
                involved_entities_set.add(dev["device_id"])
                involved_entities_set.update(co_accts[:5])
                verified_facts.append(
                    EvidenceItem(
                        evidence_id=f"EV-INFRA-{infra_idx:02d}",
                        category="FACT_INFRASTRUCTURE",
                        title=f"Shared Device Telemetry ({dev['label']})",
                        description=(
                            f"Device fingerprint {dev['label']} was observed authenticating both "
                            f"{strip_prefix(focal_entity)} and {len(co_accts)} other account(s): "
                            f"{', '.join(strip_prefix(a) for a in co_accts[:4])}."
                        ),
                        is_direct_fact=True,
                        confidence="HIGH",
                        related_entities=[focal_entity, dev["device_id"]] + co_accts[:4],
                    )
                )

        for ip in detail.get("ips", []):
            if ip.get("is_shared"):
                infra_idx += 1
                co_accts = ip.get("co_using_accounts", [])
                involved_entities_set.add(ip["ip_id"])
                involved_entities_set.update(co_accts[:5])
                verified_facts.append(
                    EvidenceItem(
                        evidence_id=f"EV-INFRA-{infra_idx:02d}",
                        category="FACT_INFRASTRUCTURE",
                        title=f"Shared IP Session ({ip['label']})",
                        description=(
                            f"IP address {ip['label']} originated sessions across {len(co_accts) + 1} "
                            f"distinct accounts including {strip_prefix(focal_entity)}."
                        ),
                        is_direct_fact=True,
                        confidence="MEDIUM",
                        related_entities=[focal_entity, ip["ip_id"]] + co_accts[:4],
                    )
                )

        # 3. Analytical Pattern & ML Detections
        analytical_inferences: List[str] = []
        for pidx, det in enumerate(related_dets[:6], start=1):
            involved_entities_set.update(det.involved_entities[:8])
            for tid in det.supporting_transactions[:10]:
                if tid not in supporting_tx_ids:
                    supporting_tx_ids.append(tid)
            if "ordered_chain" in det.metrics:
                suspicious_paths.append(det.metrics["ordered_chain"])
            elif "ordered_cycle" in det.metrics:
                suspicious_paths.append(det.metrics["ordered_cycle"])

            ev_id = f"EV-PAT-{pidx:02d}"
            verified_facts.append(
                EvidenceItem(
                    evidence_id=ev_id,
                    category="ANALYTICAL_PATTERN",
                    title=f"{det.pattern_label} ({det.detection_id})",
                    description=det.summary,
                    is_direct_fact=False,
                    confidence="HIGH" if det.risk_score >= 78 else "MEDIUM",
                    related_entities=det.involved_entities[:6],
                    supporting_transactions=det.supporting_transactions[:8],
                    amount=det.total_amount,
                    metadata={"detection_id": det.detection_id, "pattern_type": det.pattern_type},
                )
            )
            analytical_inferences.append(
                f"[{ev_id}] {det.pattern_label} (Score {det.risk_score}/100): {det.explanation}"
            )

        risk_data = detail.get("risk", {})
        composite_score = float(
            focal_detection.risk_score
            if focal_detection
            else risk_data.get("risk_score", 24.0)
        )
        ml_anom = float(risk_data.get("ml_anomaly_score", 15.0))
        if ml_anom >= 50.0:
            verified_facts.append(
                EvidenceItem(
                    evidence_id="EV-ML-01",
                    category="ML_ANOMALY",
                    title=f"Isolation Forest Behavioral Anomaly ({ml_anom:.1f}/100)",
                    description=(
                        f"Unsupervised Isolation Forest scored {strip_prefix(focal_entity)} at "
                        f"{ml_anom:.1f}/100 based on amount MAD z-score, velocity, and reuse telemetry."
                    ),
                    is_direct_fact=False,
                    confidence="MEDIUM",
                    related_entities=[focal_entity],
                )
            )
            analytical_inferences.append(
                f"[EV-ML-01] Unsupervised behavioral anomaly elevation ({ml_anom:.1f}/100) indicates atypical transfer velocity or amount dispersion relative to peer baseline (not standalone proof of illicit intent)."
            )

        if composite_score >= 75:
            priority = "CRITICAL"
        elif composite_score >= 55:
            priority = "HIGH"
        elif composite_score >= 32:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # 4. Competing Hypotheses Generation (Suspicious vs. Benign Alternatives)
        hypotheses = self._build_competing_hypotheses(
            focal_entity, detail, related_dets, verified_facts, composite_score
        )

        alt_explanations = []
        for det in related_dets:
            for alt in det.alternative_explanations:
                if alt not in alt_explanations:
                    alt_explanations.append(alt)
        if not alt_explanations:
            alt_explanations = [
                "Standard commercial or retail transfer activity within expected operational variance.",
                "Shared network gateway (corporate NAT, mobile carrier CGNAT, or public Wi-Fi) explaining IP overlap without entity coordination.",
            ]

        evidence_limitations = [
            "KYC beneficial-ownership records, corporate registry filings, and legal customer identities are outside transaction telemetry and require internal core-banking lookup.",
            "Device hash and IP correlations establish technical session overlap, not verified common legal control.",
            "Isolation Forest anomaly scores quantify statistical rarity rather than calibrated criminal probability.",
        ]
        if has_synthetic and has_real:
            provenance_note = "Hybrid Evidence Context: Contains both real dataset records and controlled synthetic typology scenario records (explicitly tagged per transaction)."
        elif has_synthetic:
            provenance_note = "Controlled Synthetic Typology Scenario: Generated specifically to validate multi-hop financial-crime network reasoning."
        else:
            provenance_note = "Real Dataset Provenance: All evaluated transactions originate from ingested dataset records."

        recommended_actions = self._build_recommended_actions(
            focal_entity, related_dets, priority
        )

        # 5. Executive Narrative (Optional Grounded LLM with Deterministic Fallback)
        exec_summary, gen_mode, provider_used = self._synthesize_narrative(
            focal_entity=focal_entity,
            priority=priority,
            composite_score=composite_score,
            verified_facts=verified_facts,
            hypotheses=hypotheses,
            total_vol=total_vol,
            use_llm=use_llm_if_available,
        )

        inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        return InvestigationReport(
            investigation_id=inv_id,
            target_id=target_id,
            target_type=target_type,
            created_at=_utc_now(),
            generation_mode=gen_mode,
            llm_provider=provider_used,
            overall_priority=priority,
            composite_risk_score=round(composite_score, 1),
            executive_summary=exec_summary,
            involved_entities=sorted(involved_entities_set),
            suspicious_paths=suspicious_paths,
            supporting_transactions=supporting_tx_ids[:25],
            total_volume_analyzed=round(total_vol, 2),
            currency="USD",
            time_span={
                "start": min(timestamps) if timestamps else None,
                "end": max(timestamps) if timestamps else None,
            },
            verified_facts=verified_facts,
            analytical_inferences=analytical_inferences,
            hypotheses=hypotheses,
            alternative_explanations=alt_explanations[:5],
            evidence_limitations=evidence_limitations,
            recommended_actions=recommended_actions,
            data_provenance_note=provenance_note,
            notes=[],
        )

    def _build_competing_hypotheses(
        self,
        focal_entity: str,
        detail: Dict[str, Any],
        related_dets: List[PatternDetection],
        facts: List[EvidenceItem],
        composite_score: float,
    ) -> List[HypothesisEvaluation]:
        tx_ev_ids = [f.evidence_id for f in facts if f.category == "FACT_TRANSACTION"][:4]
        infra_ev_ids = [f.evidence_id for f in facts if f.category == "FACT_INFRASTRUCTURE"]
        pat_ev_ids = [f.evidence_id for f in facts if f.category == "ANALYTICAL_PATTERN"]
        pattern_types = {d.pattern_type for d in related_dets}
        hyps: List[HypothesisEvaluation] = []

        if "RAPID_PASS_THROUGH" in pattern_types or "MULE_ACCOUNT_INDICATOR" in pattern_types:
            hyps.append(
                HypothesisEvaluation(
                    hypothesis_id="HYP-01",
                    title="Coordinated Transit Mule / Multi-Hop Layering Conduit",
                    category="SUSPICIOUS_TYPOLOGY",
                    description=(
                        f"{strip_prefix(focal_entity)} may be acting as an intermediary transit account receiving "
                        f"aggregated inflows and rapidly forwarding ~95%+ of principal along a multi-hop chain to obscure fund origin."
                    ),
                    confidence="HIGH" if infra_ev_ids else "MODERATE",
                    supporting_evidence=pat_ev_ids + tx_ev_ids[:3] + infra_ev_ids[:1],
                    contradicting_evidence=(
                        ["No shared device telemetry observed across downstream counterparties."]
                        if not infra_ev_ids
                        else ["No prior historical chargeback or confirmed law-enforcement subpoena attached in ledger."]
                    ),
                    missing_evidence=[
                        "KYC onboarding relationship & stated occupation/business purpose for involved accounts.",
                        "Source-of-funds documentation for upstream feeder transfers.",
                    ],
                    recommended_next_step=(
                        "Pull KYC beneficial-ownership profiles for all chain intermediaries and compare login ASN / device fingerprints across the full 30-day window."
                    ),
                )
            )

        if "CIRCULAR_FLOW" in pattern_types:
            hyps.append(
                HypothesisEvaluation(
                    hypothesis_id=f"HYP-0{len(hyps)+1}",
                    title="Circular Round-Tripping / Artificial Volume Wash Ring",
                    category="SUSPICIOUS_TYPOLOGY",
                    description=(
                        f"Closed directed transfer loop involving {strip_prefix(focal_entity)} returns capital "
                        f"to the originating entity with minimal attrition, consistent with wash trading, invoice inflation, or layering."
                    ),
                    confidence="HIGH",
                    supporting_evidence=pat_ev_ids + tx_ev_ids[:4],
                    contradicting_evidence=[
                        "Transfers occurred over electronic rails with recorded counterparty identifiers rather than cash structuring."
                    ],
                    missing_evidence=[
                        "Commercial invoices or underlying trade contracts justifying reciprocal B2B settlement."
                    ],
                    recommended_next_step=(
                        "Request underlying invoice documentation and check whether all ring participants share common corporate directors or registered agents."
                    ),
                )
            )

        if "FAN_IN" in pattern_types or "FAN_OUT" in pattern_types:
            hyps.append(
                HypothesisEvaluation(
                    hypothesis_id=f"HYP-0{len(hyps)+1}",
                    title="Unregistered Aggregation & Smurfing Distribution Hub",
                    category="SUSPICIOUS_TYPOLOGY",
                    description=(
                        f"High counterparty fan-in/fan-out around {strip_prefix(focal_entity)} suggests structured "
                        f"collection from multiple feeders followed by rapid payout dispersion."
                    ),
                    confidence="MODERATE" if composite_score < 75 else "HIGH",
                    supporting_evidence=pat_ev_ids + tx_ev_ids[:3],
                    contradicting_evidence=[
                        "Commercial payment facilitators and marketplace escrow accounts exhibit structurally similar hub-and-spoke topologies."
                    ],
                    missing_evidence=[
                        "Merchant license classification and expected monthly turnover declared at account opening."
                    ],
                    recommended_next_step=(
                        "Verify whether the account holds an approved Payment Service Provider / Money Services Business designation."
                    ),
                )
            )

        if infra_ev_ids and not hyps:
            hyps.append(
                HypothesisEvaluation(
                    hypothesis_id="HYP-01",
                    title="Multi-Account Operator Sharing Device or Proxy Infrastructure",
                    category="SUSPICIOUS_TYPOLOGY",
                    description=(
                        f"Multiple ostensibly independent accounts share session hardware/network identifiers with {strip_prefix(focal_entity)}."
                    ),
                    confidence="MODERATE",
                    supporting_evidence=infra_ev_ids + tx_ev_ids[:2],
                    contradicting_evidence=[
                        "Absence of circular or multi-hop fund transfers directly linking all co-located accounts."
                    ],
                    missing_evidence=[
                        "Browser user-agent strings, biometric session tokens, and corporate IP subnet ownership records."
                    ],
                    recommended_next_step=(
                        "Perform ASN/WHOIS lookup on shared IP and inspect whether accounts belong to employees of the same corporate client."
                    ),
                )
            )

        # Always include a rigorous Benign Operational Alternative Hypothesis!
        hyps.append(
            HypothesisEvaluation(
                hypothesis_id=f"HYP-0{len(hyps)+1}",
                title="Legitimate Commercial Settlement, Treasury Sweep, or Shared Enterprise NAT",
                category="BENIGN_ALTERNATIVE",
                description=(
                    f"Observed activity around {strip_prefix(focal_entity)} could reflect authorized commercial "
                    f"treasury sweeping, batch vendor/payroll settlement, or multiple legitimate users behind a shared corporate/ISP NAT gateway."
                ),
                confidence="HIGH" if composite_score < 45 else "LOW",
                supporting_evidence=tx_ev_ids[:2] or ["Standard electronic payment rail settlement."],
                contradicting_evidence=(
                    pat_ev_ids + infra_ev_ids
                    if (pat_ev_ids or infra_ev_ids)
                    else ["No high-severity structural contradictions detected."]
                ),
                missing_evidence=[
                    "Customer-supplied commercial contract, payroll schedule, or enterprise static-IP attestation."
                ],
                recommended_next_step=(
                    "Cross-check historical 90-day account baseline and confirm whether counterparties are established recurring vendors before escalating."
                ),
            )
        )

        return hyps

    def _build_recommended_actions(
        self, focal_entity: str, related_dets: List[PatternDetection], priority: str
    ) -> List[str]:
        actions = [
            f"1. Human KYC & Beneficial Ownership Review: Inspect core-banking onboarding records for {strip_prefix(focal_entity)} and immediate 1-hop counterparties (do NOT auto-freeze without human review).",
        ]
        ptypes = {d.pattern_type for d in related_dets}
        if "SHARED_DEVICE" in ptypes or "SHARED_IP" in ptypes:
            actions.append(
                "2. Session Telemetry Audit: Correlate full device fingerprint attributes, ASN/ISP classification (residential vs. commercial VPN/proxy), and login timestamps across linked accounts."
            )
        if "RAPID_PASS_THROUGH" in ptypes or "CIRCULAR_FLOW" in ptypes:
            actions.append(
                "3. End-to-End Fund Tracing: Trace upstream origin of initial inflows and downstream cash-out/exchange endpoints across the multi-hop path."
            )
        actions.append(
            f"4. Case Disposition Decision: Assign to FIU analyst queue ({priority} priority) to request supporting commercial documentation or prepare internal SAR draft if suspicions are corroborated."
        )
        return actions

    def _synthesize_narrative(
        self,
        focal_entity: str,
        priority: str,
        composite_score: float,
        verified_facts: List[EvidenceItem],
        hypotheses: List[HypothesisEvaluation],
        total_vol: float,
        use_llm: bool,
    ) -> Tuple[str, str, Optional[str]]:
        fact_citations = ", ".join(f.evidence_id for f in verified_facts[:5])
        deterministic_summary = (
            f"Network investigation of {strip_prefix(focal_entity)} yielded a {priority} review priority "
            f"(composite hybrid score: {composite_score:.1f}/100) across ${total_vol:,.2f} in examined ledger flow. "
            f"Grounded evidence ({fact_citations or 'baseline ledger telemetry'}) separates verified transaction/session "
            f"observations from {len(hypotheses)} competing analytical hypotheses, balancing potential coordinated "
            f"typology indicators against plausible benign commercial or shared-network explanations. "
            f"Human analyst verification of KYC ownership and economic purpose is required prior to any account action."
        )

        if not use_llm or (not self.has_gemini and not self.has_openai):
            return deterministic_summary, "deterministic_evidence_engine", None

        prompt_facts = [
            {"id": f.evidence_id, "title": f.title, "desc": f.description, "direct_fact": f.is_direct_fact}
            for f in verified_facts[:8]
        ]
        prompt_text = (
            "You are a senior Financial Intelligence Unit (FIU) investigative co-pilot. "
            "Write a concise 3-4 sentence executive investigation summary grounded STRICTLY in the provided evidence JSON. "
            "Cite exact evidence IDs in brackets like [EV-TX-01] or [EV-PAT-01]. "
            "Never invent transactions, never declare confirmed guilt, and explicitly mention that benign explanations must be ruled out by a human analyst.\n\n"
            f"Target: {focal_entity} | Priority: {priority} | Risk Score: {composite_score}/100 | Volume: ${total_vol:,.2f}\n"
            f"Evidence JSON: {json.dumps(prompt_facts)}"
        )

        try:
            if self.has_gemini:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                resp = httpx.post(
                    url,
                    json={"contents": [{"parts": [{"text": prompt_text}]}]},
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                        .strip()
                    )
                    if text:
                        return text, "llm_grounded", f"Gemini ({GEMINI_MODEL})"

            if self.has_openai:
                resp = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": OPENAI_MODEL,
                        "messages": [{"role": "user", "content": prompt_text}],
                        "temperature": 0.2,
                    },
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    if text:
                        return text, "llm_grounded", f"OpenAI ({OPENAI_MODEL})"
        except Exception:
            pass

        return deterministic_summary, "deterministic_evidence_engine", None

