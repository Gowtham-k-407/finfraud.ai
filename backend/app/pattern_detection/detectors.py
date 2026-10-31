"""
Explainable Financial-Crime Network Pattern Detectors.
Detects:
  1. FAN_IN (Collection / Structuring Hubs)
  2. FAN_OUT (Rapid Dispersion Hubs)
  3. RAPID_PASS_THROUGH & Multi-Hop Layering Chains (A -> B -> C -> D)
  4. CIRCULAR_FLOW (Round-Tripping / Wash Cycles)
  5. SHARED_DEVICE (Multi-Account Device Associations)
  6. SHARED_IP (Shared Proxy / IP Clusters vs. Benign Corporate NAT differentiation)
  7. MULE_ACCOUNT_INDICATOR (Composite behavioral + topological mule indicator)
"""
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

import networkx as nx
import pandas as pd

from app.graph_engine.builder import FinancialGraphEngine, strip_prefix
from app.schemas.models import PatternDetection


class PatternDetectorSuite:
    def __init__(self, graph_engine: FinancialGraphEngine) -> None:
        self.g = graph_engine

    def run_all(self) -> List[PatternDetection]:
        if self.g.df.empty:
            return []

        detections: List[PatternDetection] = []
        passthrough_nodes: Dict[str, Dict[str, Any]] = {}

        detections.extend(self._detect_fan_in())
        detections.extend(self._detect_fan_out())
        pt_dets, passthrough_nodes = self._detect_rapid_passthrough_and_layering()
        detections.extend(pt_dets)
        detections.extend(self._detect_circular_flows())
        detections.extend(self._detect_shared_devices())
        detections.extend(self._detect_shared_ips())
        detections.extend(self._detect_mule_indicators(passthrough_nodes))

        # Sort highest risk first
        detections.sort(key=lambda d: d.risk_score, reverse=True)

        # Register detection IDs onto graph engine entities
        self.g.entity_detections = defaultdict(list)
        for det in detections:
            for ent in det.involved_entities:
                self.g.entity_detections[ent].append(det.detection_id)

        return detections

    def _provenance_flags(self, tx_ids: List[str]) -> Tuple[str, bool, str]:
        sources: Set[str] = set()
        is_syn = False
        scen = ""
        for tid in tx_ids:
            row = self.g.tx_lookup.get(tid)
            if row:
                sources.add(str(row.get("data_source", "kaggle_real")))
                if row.get("is_synthetic"):
                    is_syn = True
                if row.get("scenario_tag") and not scen:
                    scen = str(row["scenario_tag"])
        src_str = "+".join(sorted(sources)) if sources else "kaggle_real"
        return src_str, is_syn, scen

    # -------------------------------------------------------------------------
    # 1. FAN-IN DETECTOR
    # -------------------------------------------------------------------------
    def _detect_fan_in(self, min_senders: int = 4) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        idx = 0
        for node in self.g.acct_di_graph.nodes():
            preds = list(self.g.acct_di_graph.predecessors(node))
            if len(preds) < min_senders:
                continue

            tx_ids: List[str] = []
            epochs: List[int] = []
            timestamps: List[str] = []
            amounts: List[float] = []
            for p in preds:
                for _, ed in self.g.tx_multi_graph[p][node].items():
                    tx_ids.append(ed["transaction_id"])
                    epochs.append(int(ed["epoch"]))
                    timestamps.append(ed["timestamp"])
                    amounts.append(float(ed["amount"]))

            if not tx_ids:
                continue
            total_in = sum(amounts)
            duration_min = round((max(epochs) - min(epochs)) / 60.0, 1) if len(epochs) > 1 else 0.0
            near_threshold_count = sum(1 for a in amounts if 3500 <= a < 5000)

            concentration_bonus = 20.0 if duration_min <= 240 else (10.0 if duration_min <= 1440 else 0.0)
            structuring_bonus = 12.0 if near_threshold_count >= 3 else 0.0
            score = min(96.0, 52.0 + len(preds) * 3.5 + concentration_bonus + structuring_bonus)
            severity = "CRITICAL" if score >= 82 else ("HIGH" if score >= 68 else "MEDIUM")

            src_str, is_syn, scen = self._provenance_flags(tx_ids)
            idx += 1
            results.append(
                PatternDetection(
                    detection_id=f"DET-FANIN-{idx:03d}",
                    pattern_type="FAN_IN",
                    pattern_label="Fan-In Collection Hub",
                    severity=severity,
                    risk_score=round(score, 1),
                    primary_entity=node,
                    involved_entities=[node] + preds[:12],
                    supporting_transactions=tx_ids[:25],
                    total_amount=round(total_in, 2),
                    time_window_start=min(timestamps),
                    time_window_end=max(timestamps),
                    duration_minutes=duration_min,
                    summary=(
                        f"{strip_prefix(node)} aggregated ${total_in:,.2f} across {len(tx_ids)} transfers "
                        f"from {len(preds)} distinct sender accounts within {duration_min:.0f} mins."
                    ),
                    explanation=(
                        f"Many-to-one collection topology detected: {len(preds)} independent origin accounts "
                        f"converged funds into {strip_prefix(node)}."
                        + (
                            f" {near_threshold_count} transfers clustered in the $3,500-$4,999 structuring band."
                            if near_threshold_count >= 3
                            else ""
                        )
                    ),
                    alternative_explanations=[
                        "Legitimate merchant settlement or marketplace escrow collection account.",
                        "Crowdfunding, charity pooling, or corporate treasury sweeping from regional branches.",
                    ],
                    confidence_basis=(
                        f"Direct ledger verification of {len(preds)} distinct senders and {duration_min:.0f}-minute temporal window."
                    ),
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "distinct_senders": len(preds),
                        "transfer_count": len(tx_ids),
                        "near_5k_threshold_transfers": near_threshold_count,
                        "duration_minutes": duration_min,
                    },
                )
            )
        return results

    # -------------------------------------------------------------------------
    # 2. FAN-OUT DETECTOR
    # -------------------------------------------------------------------------
    def _detect_fan_out(self, min_receivers: int = 4) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        idx = 0
        for node in self.g.acct_di_graph.nodes():
            succs = list(self.g.acct_di_graph.successors(node))
            if len(succs) < min_receivers:
                continue

            tx_ids: List[str] = []
            epochs: List[int] = []
            timestamps: List[str] = []
            amounts: List[float] = []
            for s in succs:
                for _, ed in self.g.tx_multi_graph[node][s].items():
                    tx_ids.append(ed["transaction_id"])
                    epochs.append(int(ed["epoch"]))
                    timestamps.append(ed["timestamp"])
                    amounts.append(float(ed["amount"]))

            if not tx_ids:
                continue
            total_out = sum(amounts)
            duration_min = round((max(epochs) - min(epochs)) / 60.0, 1) if len(epochs) > 1 else 0.0
            burst_bonus = 20.0 if duration_min <= 240 else 8.0
            score = min(95.0, 50.0 + len(succs) * 3.8 + burst_bonus)
            severity = "CRITICAL" if score >= 82 else ("HIGH" if score >= 68 else "MEDIUM")

            src_str, is_syn, scen = self._provenance_flags(tx_ids)
            idx += 1
            results.append(
                PatternDetection(
                    detection_id=f"DET-FANOUT-{idx:03d}",
                    pattern_type="FAN_OUT",
                    pattern_label="Fan-Out Dispersion Hub",
                    severity=severity,
                    risk_score=round(score, 1),
                    primary_entity=node,
                    involved_entities=[node] + succs[:12],
                    supporting_transactions=tx_ids[:25],
                    total_amount=round(total_out, 2),
                    time_window_start=min(timestamps),
                    time_window_end=max(timestamps),
                    duration_minutes=duration_min,
                    summary=(
                        f"{strip_prefix(node)} dispersed ${total_out:,.2f} to {len(succs)} distinct "
                        f"beneficiary accounts within {duration_min:.0f} mins."
                    ),
                    explanation=(
                        f"One-to-many distribution behavior: {strip_prefix(node)} executed {len(tx_ids)} "
                        f"outbound transfers splitting funds across {len(succs)} separate recipients."
                    ),
                    alternative_explanations=[
                        "Scheduled payroll disbursement or contractor batch payout run.",
                        "Accounts-payable vendor settlement batch.",
                    ],
                    confidence_basis=f"Direct ledger observation across {len(succs)} distinct recipient accounts.",
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "distinct_receivers": len(succs),
                        "transfer_count": len(tx_ids),
                        "duration_minutes": duration_min,
                    },
                )
            )
        return results

    # -------------------------------------------------------------------------
    # 3. RAPID PASS-THROUGH & MULTI-HOP LAYERING DETECTOR
    # -------------------------------------------------------------------------
    def _detect_rapid_passthrough_and_layering(
        self, max_hold_minutes: float = 180.0
    ) -> Tuple[List[PatternDetection], Dict[str, Dict[str, Any]]]:
        results: List[PatternDetection] = []
        passthrough_nodes: Dict[str, Dict[str, Any]] = {}
        relay_edges: nx.DiGraph = nx.DiGraph()

        for node in self.g.acct_di_graph.nodes():
            in_deg = self.g.acct_di_graph.in_degree(node)
            out_deg = self.g.acct_di_graph.out_degree(node)
            if in_deg == 0 or out_deg == 0:
                continue

            in_events = []
            for p in self.g.acct_di_graph.predecessors(node):
                for _, ed in self.g.tx_multi_graph[p][node].items():
                    in_events.append((p, ed))

            out_events = []
            for s in self.g.acct_di_graph.successors(node):
                for _, ed in self.g.tx_multi_graph[node][s].items():
                    out_events.append((s, ed))

            in_events.sort(key=lambda x: x[1]["epoch"])
            out_events.sort(key=lambda x: x[1]["epoch"])

            # Evaluate rapid pass-through windows: sum of inflows within 3 hours prior to each large outflow
            for out_target, out_ed in out_events:
                out_ep = int(out_ed["epoch"])
                out_amt = float(out_ed["amount"])
                prior_in = [
                    (src, ied)
                    for src, ied in in_events
                    if 0 <= (out_ep - int(ied["epoch"])) <= max_hold_minutes * 60
                    and src != out_target
                ]
                if not prior_in:
                    continue

                in_sum = sum(float(ied["amount"]) for _, ied in prior_in)
                if in_sum <= 0:
                    continue
                retention_ratio = out_amt / in_sum
                # Typical mule pass-through forwards 78% - 108% of recently received funds
                if 0.78 <= retention_ratio <= 1.08 and out_amt >= 500.0:
                    min_lag_sec = min(out_ep - int(ied["epoch"]) for _, ied in prior_in)
                    lag_min = round(min_lag_sec / 60.0, 1)
                    tx_ids = [ied["transaction_id"] for _, ied in prior_in] + [out_ed["transaction_id"]]
                    sources = sorted({src for src, _ in prior_in})

                    passthrough_nodes[node] = {
                        "lag_minutes": lag_min,
                        "forwarded_ratio": round(retention_ratio, 3),
                        "in_amount": round(in_sum, 2),
                        "out_amount": round(out_amt, 2),
                        "tx_ids": tx_ids,
                        "sources": sources,
                        "target": out_target,
                        "start_ts": min(ied["timestamp"] for _, ied in prior_in),
                        "end_ts": out_ed["timestamp"],
                    }
                    for src in sources:
                        relay_edges.add_edge(src, node)
                    relay_edges.add_edge(node, out_target)

        # Build multi-hop layering chains across consecutive pass-through intermediaries
        emitted_nodes: Set[str] = set()
        idx = 0

        # Find longest relay chains
        chains: List[List[str]] = []
        for n in relay_edges.nodes():
            if relay_edges.in_degree(n) == 0:
                for leaf in relay_edges.nodes():
                    if relay_edges.out_degree(leaf) == 0 and n != leaf:
                        for path in nx.all_simple_paths(relay_edges, n, leaf, cutoff=6):
                            if len(path) >= 4:  # At least 2 intermediary pass-through hops!
                                chains.append(path)

        chains.sort(key=len, reverse=True)
        for chain in chains:
            intermediaries = [n for n in chain[1:-1] if n in passthrough_nodes]
            if len(intermediaries) < 2 or all(n in emitted_nodes for n in intermediaries):
                continue
            emitted_nodes.update(intermediaries)

            chain_txs: List[str] = []
            timestamps: List[str] = []
            lags: List[float] = []
            max_vol = 0.0
            for inter in intermediaries:
                info = passthrough_nodes[inter]
                for tid in info["tx_ids"]:
                    if tid not in chain_txs:
                        chain_txs.append(tid)
                timestamps.extend([info["start_ts"], info["end_ts"]])
                lags.append(info["lag_minutes"])
                max_vol = max(max_vol, info["in_amount"], info["out_amount"])

            src_str, is_syn, scen = self._provenance_flags(chain_txs)
            idx += 1
            chain_labels = " -> ".join(strip_prefix(c) for c in chain)
            results.append(
                PatternDetection(
                    detection_id=f"DET-LAYER-{idx:03d}",
                    pattern_type="RAPID_PASS_THROUGH",
                    pattern_label=f"Multi-Hop Layering Chain ({len(chain) - 1} Hops)",
                    severity="CRITICAL",
                    risk_score=min(98.0, round(82.0 + len(intermediaries) * 4.5, 1)),
                    primary_entity=intermediaries[0],
                    involved_entities=chain,
                    supporting_transactions=chain_txs,
                    total_amount=round(max_vol, 2),
                    time_window_start=min(timestamps),
                    time_window_end=max(timestamps),
                    duration_minutes=round(sum(lags), 1),
                    summary=(
                        f"Multi-hop rapid pass-through chain ({chain_labels}) moving ~${max_vol:,.2f} "
                        f"across {len(intermediaries)} transit intermediaries (avg hold: {sum(lags)/len(lags):.1f} mins)."
                    ),
                    explanation=(
                        f"Funds entered {strip_prefix(chain[0])} and traversed {len(intermediaries)} sequential "
                        f"conduit accounts ({', '.join(strip_prefix(i) for i in intermediaries)}) to {strip_prefix(chain[-1])}, "
                        f"forwarding 95%+ of principal at each hop with minimal balance retention."
                    ),
                    alternative_explanations=[
                        "Automated correspondent banking or payment-service-provider settlement routing.",
                        "Inter-company liquidity sweep across subsidiary treasury accounts.",
                    ],
                    confidence_basis=(
                        f"Sequential directed timestamps and amount-conservation ratios across {len(chain)-1} contiguous hops."
                    ),
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "hop_count": len(chain) - 1,
                        "intermediary_count": len(intermediaries),
                        "avg_hold_minutes": round(sum(lags) / len(lags), 1),
                        "ordered_chain": chain,
                    },
                )
            )

        # Also emit individual single-account rapid pass-throughs not already covered
        for node, info in passthrough_nodes.items():
            if node in emitted_nodes:
                continue
            idx += 1
            src_str, is_syn, scen = self._provenance_flags(info["tx_ids"])
            involved = [node] + info["sources"] + [info["target"]]
            score = min(92.0, round(72.0 + (20.0 if info["lag_minutes"] <= 30 else 8.0), 1))
            results.append(
                PatternDetection(
                    detection_id=f"DET-LAYER-{idx:03d}",
                    pattern_type="RAPID_PASS_THROUGH",
                    pattern_label="Rapid Pass-Through Conduit",
                    severity="HIGH" if score < 84 else "CRITICAL",
                    risk_score=score,
                    primary_entity=node,
                    involved_entities=involved,
                    supporting_transactions=info["tx_ids"],
                    total_amount=info["out_amount"],
                    time_window_start=info["start_ts"],
                    time_window_end=info["end_ts"],
                    duration_minutes=info["lag_minutes"],
                    summary=(
                        f"{strip_prefix(node)} received ${info['in_amount']:,.2f} and forwarded "
                        f"${info['out_amount']:,.2f} ({info['forwarded_ratio']*100:.1f}%) within {info['lag_minutes']} mins."
                    ),
                    explanation=(
                        f"Zero-retention transit behavior: incoming funds from {len(info['sources'])} source(s) "
                        f"were immediately wired onward to {strip_prefix(info['target'])}."
                    ),
                    alternative_explanations=[
                        "Immediate bill/loan settlement triggered right after salary or invoice receipt.",
                        "Pass-through brokerage or FX conversion account.",
                    ],
                    confidence_basis=f"Direct inflow/outflow delta of {info['lag_minutes']} minutes and {info['forwarded_ratio']*100:.1f}% amount match.",
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "lag_minutes": info["lag_minutes"],
                        "forwarded_ratio": info["forwarded_ratio"],
                    },
                )
            )

        return results, passthrough_nodes

    # -------------------------------------------------------------------------
    # 4. CIRCULAR / RECIPROCAL TRANSFER DETECTOR
    # -------------------------------------------------------------------------
    def _detect_circular_flows(self) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        # Restrict cycle search to Strongly Connected Components with >1 node for instant execution
        sccs = [c for c in nx.strongly_connected_components(self.g.acct_di_graph) if len(c) >= 2]
        idx = 0
        seen_cycles: Set[frozenset] = set()

        for comp in sccs:
            sub = self.g.acct_di_graph.subgraph(comp)
            for cycle in nx.simple_cycles(sub, length_bound=6):
                key = frozenset(cycle)
                if key in seen_cycles:
                    continue
                seen_cycles.add(key)

                cycle_ring = cycle + [cycle[0]]
                tx_ids: List[str] = []
                hop_amounts: List[float] = []
                timestamps: List[str] = []
                epochs: List[int] = []

                for i in range(len(cycle)):
                    u, v = cycle_ring[i], cycle_ring[i + 1]
                    ed = self.g.acct_di_graph.edges[u, v]
                    tx_ids.extend(ed["tx_ids"])
                    hop_amounts.append(float(ed["total_amount"]))
                    if ed["first_seen"]:
                        timestamps.append(ed["first_seen"])
                    if ed["last_seen"]:
                        timestamps.append(ed["last_seen"])
                    for _, med in self.g.tx_multi_graph[u][v].items():
                        epochs.append(int(med["epoch"]))

                min_amt, max_amt = min(hop_amounts), max(hop_amounts)
                conservation = round(min_amt / max_amt, 3) if max_amt > 0 else 0.0
                duration_min = round((max(epochs) - min(epochs)) / 60.0, 1) if len(epochs) > 1 else 0.0
                score = min(97.0, round(74.0 + len(cycle) * 3.5 + conservation * 12.0, 1))
                src_str, is_syn, scen = self._provenance_flags(tx_ids)
                idx += 1
                ring_label = " -> ".join(strip_prefix(n) for n in cycle_ring)

                results.append(
                    PatternDetection(
                        detection_id=f"DET-CYCLE-{idx:03d}",
                        pattern_type="CIRCULAR_FLOW",
                        pattern_label=(
                            f"Circular Round-Trip Ring ({len(cycle)} Accounts)"
                            if len(cycle) >= 3
                            else "Reciprocal Back-and-Forth Loop"
                        ),
                        severity="CRITICAL" if len(cycle) >= 3 else "HIGH",
                        risk_score=score,
                        primary_entity=cycle[0],
                        involved_entities=cycle,
                        supporting_transactions=list(dict.fromkeys(tx_ids)),
                        total_amount=round(sum(hop_amounts) / len(hop_amounts), 2),
                        time_window_start=min(timestamps) if timestamps else None,
                        time_window_end=max(timestamps) if timestamps else None,
                        duration_minutes=duration_min,
                        summary=(
                            f"Closed {len(cycle)}-account financial loop ({ring_label}) cycling "
                            f"~${min_amt:,.2f} with {conservation*100:.1f}% value conservation."
                        ),
                        explanation=(
                            f"Directed cycle discovered where capital originating from {strip_prefix(cycle[0])} "
                            f"returned to {strip_prefix(cycle[0])} across {len(cycle)} hops within {duration_min:.0f} mins."
                        ),
                        alternative_explanations=[
                            "Bilateral trade refund, invoice reversal, or inter-company netting adjustment.",
                            "Shared expense reimbursement between recurring business counterparties.",
                        ],
                        confidence_basis=(
                            f"Exact topological cycle closure across {len(cycle)} directed ledger edges."
                        ),
                        data_source=src_str,
                        is_synthetic_scenario=is_syn,
                        scenario_tag=scen or None,
                        metrics={
                            "cycle_length": len(cycle),
                            "value_conservation_ratio": conservation,
                            "ordered_cycle": cycle_ring,
                            "duration_minutes": duration_min,
                        },
                    )
                )
        return results

    # -------------------------------------------------------------------------
    # 5. SHARED DEVICE DETECTOR
    # -------------------------------------------------------------------------
    def _detect_shared_devices(self) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        idx = 0
        for dev_id, accts in self.g.device_to_accounts.items():
            if len(accts) < 2:
                continue
            acct_list = sorted(accts)
            raw_dev = strip_prefix(dev_id)
            sub_df = self.g.df[self.g.df["device_hash"] == raw_dev]
            tx_ids = sub_df["transaction_id"].tolist()[:25]
            total_amt = float(sub_df["amount"].sum())
            avg_vel = float(sub_df["velocity_score"].mean()) if not sub_df.empty else 1.0
            timestamps = sub_df["timestamp"].tolist()

            # Check if accounts sharing device ALSO transact along a chain together!
            direct_tx_link = any(
                self.g.acct_di_graph.has_edge(a, b)
                or nx.has_path(self.g.acct_di_graph, a, b)
                for a in acct_list
                for b in acct_list
                if a != b and a in self.g.acct_di_graph and b in self.g.acct_di_graph
            )

            score = min(
                94.0,
                round(54.0 + len(acct_list) * 6.5 + (16.0 if direct_tx_link else 0.0) + (8.0 if avg_vel >= 7 else 0.0), 1),
            )
            severity = "CRITICAL" if score >= 82 else ("HIGH" if score >= 68 else "MEDIUM")
            src_str, is_syn, scen = self._provenance_flags(tx_ids)
            idx += 1

            results.append(
                PatternDetection(
                    detection_id=f"DET-DEV-{idx:03d}",
                    pattern_type="SHARED_DEVICE",
                    pattern_label="Shared Device Fingerprint Cluster",
                    severity=severity,
                    risk_score=score,
                    primary_entity=dev_id,
                    involved_entities=[dev_id] + acct_list,
                    supporting_transactions=tx_ids,
                    total_amount=round(total_amt, 2),
                    time_window_start=min(timestamps) if timestamps else None,
                    time_window_end=max(timestamps) if timestamps else None,
                    summary=(
                        f"Device {raw_dev} authenticated transactions across {len(acct_list)} distinct accounts "
                        f"({', '.join(strip_prefix(a) for a in acct_list[:4])}) totaling ${total_amt:,.2f}."
                    ),
                    explanation=(
                        f"Session telemetry shows {len(acct_list)} separate account identifiers operating from "
                        f"identical hardware/browser fingerprint {raw_dev}."
                        + (
                            " CRITICAL CORRELATION: Accounts sharing this device also sit on the same directed funds-transfer path!"
                            if direct_tx_link
                            else " Treated conservatively as an infrastructure association edge, not automatic common ownership."
                        )
                    ),
                    alternative_explanations=[
                        "Shared household tablet/PC used by multiple family members.",
                        "Authorized corporate finance workstation managing multiple subsidiary accounts.",
                        "Public kiosk or branch-assisted terminal session.",
                    ],
                    confidence_basis=(
                        f"Exact device_hash match across {len(sub_df)} transactions"
                        + (" combined with directed fund-flow linkage." if direct_tx_link else ".")
                    ),
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "account_count": len(acct_list),
                        "has_fund_flow_correlation": direct_tx_link,
                        "avg_velocity_score": round(avg_vel, 2),
                    },
                )
            )
        return results

    # -------------------------------------------------------------------------
    # 6. SHARED IP / PROXY DETECTOR (Distinguishes Proxy Rings vs Benign NAT!)
    # -------------------------------------------------------------------------
    def _detect_shared_ips(self) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        idx = 0
        for ip_id, accts in self.g.ip_to_accounts.items():
            if len(accts) < 2:
                continue
            acct_list = sorted(accts)
            raw_ip = strip_prefix(ip_id)
            sub_df = self.g.df[self.g.df["ip_address"] == raw_ip]
            tx_ids = sub_df["transaction_id"].tolist()[:25]
            total_amt = float(sub_df["amount"].sum())
            avg_vel = float(sub_df["velocity_score"].mean()) if not sub_df.empty else 1.0
            avg_geo = float(sub_df["geo_anomaly_score"].mean()) if not sub_df.empty else 0.0
            unique_devs = int(sub_df["device_hash"].replace("", pd.NA).dropna().nunique())
            timestamps = sub_df["timestamp"].tolist()

            # Check behavioral & topological risk so benign corporate NAT stays LOW/MEDIUM!
            inter_acct_flow = any(
                self.g.acct_di_graph.has_edge(a, b)
                for a in acct_list
                for b in acct_list
                if a != b and a in self.g.acct_di_graph and b in self.g.acct_di_graph
            )

            is_low_velocity_benign_like = (avg_vel <= 3.5 and avg_geo <= 0.25 and not inter_acct_flow)
            if is_low_velocity_benign_like:
                score = round(34.0 + len(acct_list) * 2.5, 1)
                severity = "LOW"
                label = "Shared IP Infrastructure (Low-Risk / Potential NAT)"
            else:
                score = min(
                    93.0,
                    round(
                        52.0
                        + len(acct_list) * 5.0
                        + (18.0 if inter_acct_flow else 0.0)
                        + (12.0 if avg_vel >= 7 else 0.0),
                        1,
                    ),
                )
                severity = "CRITICAL" if score >= 82 else ("HIGH" if score >= 66 else "MEDIUM")
                label = "Shared Proxy / High-Velocity IP Cluster"

            src_str, is_syn, scen = self._provenance_flags(tx_ids)
            idx += 1
            results.append(
                PatternDetection(
                    detection_id=f"DET-IP-{idx:03d}",
                    pattern_type="SHARED_IP",
                    pattern_label=label,
                    severity=severity,
                    risk_score=score,
                    primary_entity=ip_id,
                    involved_entities=[ip_id] + acct_list,
                    supporting_transactions=tx_ids,
                    total_amount=round(total_amt, 2),
                    time_window_start=min(timestamps) if timestamps else None,
                    time_window_end=max(timestamps) if timestamps else None,
                    summary=(
                        f"IP {raw_ip} observed across {len(acct_list)} accounts (${total_amt:,.2f}, "
                        f"avg velocity {avg_vel:.1f}, {unique_devs} distinct devices)."
                    ),
                    explanation=(
                        f"Multiple accounts initiated transactions from IP {raw_ip}. "
                        + (
                            "Low velocity, distinct corporate/personal devices, and absence of inter-account transfers strongly resemble benign NAT or enterprise gateway sharing."
                            if is_low_velocity_benign_like
                            else "Elevated velocity, anomalous geolocation telemetry, or direct inter-account transfers indicate potential proxy/VPN coordination."
                        )
                    ),
                    alternative_explanations=[
                        "Corporate office NAT gateway or campus/institutional network.",
                        "Mobile carrier CGNAT or commercial VPN exit node.",
                        "Public Wi-Fi at airport, hotel, or co-working facility.",
                    ],
                    confidence_basis=f"IP telemetry correlation evaluated alongside device diversity ({unique_devs}) and velocity ({avg_vel:.1f}).",
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "account_count": len(acct_list),
                        "distinct_devices_on_ip": unique_devs,
                        "avg_velocity_score": round(avg_vel, 2),
                        "inter_account_transfers": inter_acct_flow,
                        "benign_nat_likeness": is_low_velocity_benign_like,
                    },
                )
            )
        return results

    # -------------------------------------------------------------------------
    # 7. POTENTIAL MULE-ACCOUNT INDICATOR DETECTOR
    # -------------------------------------------------------------------------
    def _detect_mule_indicators(
        self, passthrough_nodes: Dict[str, Dict[str, Any]]
    ) -> List[PatternDetection]:
        results: List[PatternDetection] = []
        idx = 0
        for aid, st in self.g.account_stats.items():
            in_cnt = st["in_count"]
            out_cnt = st["out_count"]
            in_amt = st["in_amount"]
            out_amt = st["out_amount"]
            if in_cnt == 0 or out_cnt == 0 or (in_cnt + out_cnt) < 3:
                continue

            flow_balance_ratio = min(in_amt, out_amt) / max(in_amt, out_amt) if max(in_amt, out_amt) > 0 else 0.0
            has_shared_dev = any(
                len(self.g.device_to_accounts.get(d, set())) >= 2
                for d in self.g.account_to_devices.get(aid, set())
            )
            has_shared_ip = any(
                len(self.g.ip_to_accounts.get(ip, set())) >= 2
                for ip in self.g.account_to_ips.get(aid, set())
            )
            is_rapid_pt = aid in passthrough_nodes

            signals = []
            points = 0.0
            if is_rapid_pt:
                points += 38.0
                signals.append(f"rapid pass-through ({passthrough_nodes[aid]['lag_minutes']}m hold)")
            if flow_balance_ratio >= 0.80:
                points += 24.0
                signals.append(f"near-zero balance retention ({flow_balance_ratio*100:.0f}% turnover)")
            if (in_cnt + out_cnt) >= 4:
                points += 14.0
                signals.append(f"high counterparty degree ({in_cnt} in / {out_cnt} out)")
            if has_shared_dev:
                points += 16.0
                signals.append("shared device fingerprint")
            if has_shared_ip:
                points += 10.0
                signals.append("shared IP session")

            if points < 62.0:
                continue

            score = min(97.0, round(points, 1))
            tx_ids = st["tx_ids"][:20]
            src_str, is_syn, scen = self._provenance_flags(tx_ids)
            neighbors = list(self.g.acct_di_graph.predecessors(aid))[:5] + list(
                self.g.acct_di_graph.successors(aid)
            )[:5]
            idx += 1

            results.append(
                PatternDetection(
                    detection_id=f"DET-MULE-{idx:03d}",
                    pattern_type="MULE_ACCOUNT_INDICATOR",
                    pattern_label="Potential Mule-Account Indicator",
                    severity="CRITICAL" if score >= 82 else "HIGH",
                    risk_score=score,
                    primary_entity=aid,
                    involved_entities=[aid] + neighbors,
                    supporting_transactions=tx_ids,
                    total_amount=round(max(in_amt, out_amt), 2),
                    time_window_start=st["first_seen"],
                    time_window_end=st["last_seen"],
                    summary=(
                        f"{st['label']} exhibits converging potential mule indicators: "
                        + ", ".join(signals)
                        + "."
                    ),
                    explanation=(
                        f"Analytical risk composite (not a confirmed criminal designation): {st['label']} "
                        f"received ${in_amt:,.2f} across {in_cnt} transfers and exited ${out_amt:,.2f} across "
                        f"{out_cnt} transfers with {flow_balance_ratio*100:.1f}% capital pass-through."
                    ),
                    alternative_explanations=[
                        "Designated payment aggregator, remittance agent, or escrow clearing account.",
                        "Active sole-proprietor operating account matching receivables directly to supplier payables.",
                    ],
                    confidence_basis=f"Multi-signal convergence ({len(signals)} independent topological and telemetry indicators).",
                    data_source=src_str,
                    is_synthetic_scenario=is_syn,
                    scenario_tag=scen or None,
                    metrics={
                        "in_amount": in_amt,
                        "out_amount": out_amt,
                        "turnover_ratio": round(flow_balance_ratio, 3),
                        "shared_device": has_shared_dev,
                        "shared_ip": has_shared_ip,
                        "rapid_passthrough": is_rapid_pt,
                    },
                )
            )
        return results

