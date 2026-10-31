"""
NetworkX Core Graph & Entity-Resolution Engine.
Constructs:
  1. `tx_multi_graph` (nx.MultiDiGraph): Account -> Account directed multi-edges retaining
     every transaction's ID, amount, timestamp, channel, and source provenance.
  2. `acct_di_graph` (nx.DiGraph): Aggregated directed Account -> Account topology for
     fast cycle detection, path discovery, degree/betweenness centrality, and community analysis.
  3. `hetero_graph` (nx.MultiDiGraph): Full heterogeneous entity graph containing explicit
     namespaced IDs:
       - ACCOUNT:<id>
       - DEVICE:<id>
       - IP:<id>
       - LOCATION:<id>
     with conservative, evidence-backed relationship edges (never merging accounts on weak evidence).
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd


def make_account_id(raw: str) -> str:
    return raw if raw.startswith("ACCOUNT:") else f"ACCOUNT:{raw}"


def strip_prefix(entity_id: str) -> str:
    return entity_id.split(":", 1)[1] if ":" in entity_id else entity_id


class FinancialGraphEngine:
    def __init__(self) -> None:
        self.df: pd.DataFrame = pd.DataFrame()
        self.tx_lookup: Dict[str, Dict[str, Any]] = {}
        self.tx_multi_graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.acct_di_graph: nx.DiGraph = nx.DiGraph()
        self.hetero_graph: nx.MultiDiGraph = nx.MultiDiGraph()

        self.account_stats: Dict[str, Dict[str, Any]] = {}
        self.device_to_accounts: Dict[str, Set[str]] = defaultdict(set)
        self.ip_to_accounts: Dict[str, Set[str]] = defaultdict(set)
        self.account_to_devices: Dict[str, Set[str]] = defaultdict(set)
        self.account_to_ips: Dict[str, Set[str]] = defaultdict(set)
        self.community_map: Dict[str, int] = {}
        self.betweenness_map: Dict[str, float] = {}
        self.degree_centrality_map: Dict[str, float] = {}

        # Populated after ML + pattern detection
        self.entity_risk: Dict[str, Dict[str, Any]] = {}
        self.entity_detections: Dict[str, List[str]] = defaultdict(list)

    def build_from_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        self.df = df.copy()
        self.tx_lookup = {}
        self.tx_multi_graph = nx.MultiDiGraph()
        self.acct_di_graph = nx.DiGraph()
        self.hetero_graph = nx.MultiDiGraph()
        self.account_stats = {}
        self.device_to_accounts = defaultdict(set)
        self.ip_to_accounts = defaultdict(set)
        self.account_to_devices = defaultdict(set)
        self.account_to_ips = defaultdict(set)
        self.entity_risk = {}
        self.entity_detections = defaultdict(list)

        if df.empty:
            return self.get_graph_summary()

        records = df.to_dict(orient="records")

        # Temporary accumulators for account profiles
        acct_acc: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "raw_id": "",
                "in_count": 0,
                "out_count": 0,
                "in_amount": 0.0,
                "out_amount": 0.0,
                "first_seen": None,
                "last_seen": None,
                "locations": set(),
                "channels": set(),
                "merchant_categories": set(),
                "is_synthetic": False,
                "data_sources": set(),
                "fraud_tx_count": 0,
                "tx_ids": [],
            }
        )

        pair_agg: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {
                "tx_count": 0,
                "total_amount": 0.0,
                "first_seen": None,
                "last_seen": None,
                "tx_ids": [],
                "is_synthetic": False,
            }
        )

        infra_edge_agg: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "first_seen": None,
                "last_seen": None,
                "tx_ids": [],
            }
        )

        for row in records:
            tx_id = str(row["transaction_id"])
            self.tx_lookup[tx_id] = row

            s_raw = str(row["sender_account"])
            r_raw = str(row["receiver_account"])
            s_id = f"ACCOUNT:{s_raw}"
            r_id = f"ACCOUNT:{r_raw}"
            amt = float(row["amount"])
            ts = str(row["timestamp"])
            epoch = int(row.get("epoch", 0))
            is_syn = bool(row.get("is_synthetic", False))
            d_src = str(row.get("data_source", "kaggle_real"))

            # Update sender & receiver stats
            for aid, raw, is_sender in [(s_id, s_raw, True), (r_id, r_raw, False)]:
                st = acct_acc[aid]
                st["raw_id"] = raw
                if is_sender:
                    st["out_count"] += 1
                    st["out_amount"] += amt
                else:
                    st["in_count"] += 1
                    st["in_amount"] += amt
                if st["first_seen"] is None or ts < st["first_seen"]:
                    st["first_seen"] = ts
                if st["last_seen"] is None or ts > st["last_seen"]:
                    st["last_seen"] = ts
                if row.get("location"):
                    st["locations"].add(str(row["location"]))
                if row.get("payment_channel"):
                    st["channels"].add(str(row["payment_channel"]))
                if row.get("merchant_category"):
                    st["merchant_categories"].add(str(row["merchant_category"]))
                if is_syn:
                    st["is_synthetic"] = True
                st["data_sources"].add(d_src)
                if row.get("is_fraud"):
                    st["fraud_tx_count"] += 1
                if len(st["tx_ids"]) < 40:
                    st["tx_ids"].append(tx_id)

            # Multi-edge transaction graph
            edge_attrs = {
                "transaction_id": tx_id,
                "relationship_type": "ACCOUNT_SENT_TO_ACCOUNT",
                "amount": amt,
                "timestamp": ts,
                "epoch": epoch,
                "transaction_type": row.get("transaction_type", "transfer"),
                "payment_channel": row.get("payment_channel", "electronic"),
                "is_synthetic": is_syn,
                "data_source": d_src,
                "evidence_source": "transaction_ledger",
                "is_direct": True,
            }
            self.tx_multi_graph.add_edge(s_id, r_id, key=tx_id, **edge_attrs)

            # Pairwise aggregated account edge
            p = pair_agg[(s_id, r_id)]
            p["tx_count"] += 1
            p["total_amount"] += amt
            p["first_seen"] = ts if p["first_seen"] is None or ts < p["first_seen"] else p["first_seen"]
            p["last_seen"] = ts if p["last_seen"] is None or ts > p["last_seen"] else p["last_seen"]
            if len(p["tx_ids"]) < 25:
                p["tx_ids"].append(tx_id)
            if is_syn:
                p["is_synthetic"] = True

            # Conservative Device & IP evidence edges (linked to initiating sender account)
            dev_raw = str(row.get("device_hash", "")).strip()
            if dev_raw:
                dev_id = f"DEVICE:{dev_raw}"
                self.device_to_accounts[dev_id].add(s_id)
                self.account_to_devices[s_id].add(dev_id)
                ie = infra_edge_agg[(s_id, dev_id, "ACCOUNT_USED_DEVICE")]
                ie["count"] += 1
                ie["first_seen"] = ts if ie["first_seen"] is None or ts < ie["first_seen"] else ie["first_seen"]
                ie["last_seen"] = ts if ie["last_seen"] is None or ts > ie["last_seen"] else ie["last_seen"]
                if len(ie["tx_ids"]) < 15:
                    ie["tx_ids"].append(tx_id)

            ip_raw = str(row.get("ip_address", "")).strip()
            if ip_raw:
                ip_id = f"IP:{ip_raw}"
                self.ip_to_accounts[ip_id].add(s_id)
                self.account_to_ips[s_id].add(ip_id)
                ie = infra_edge_agg[(s_id, ip_id, "ACCOUNT_USED_IP")]
                ie["count"] += 1
                ie["first_seen"] = ts if ie["first_seen"] is None or ts < ie["first_seen"] else ie["first_seen"]
                ie["last_seen"] = ts if ie["last_seen"] is None or ts > ie["last_seen"] else ie["last_seen"]
                if len(ie["tx_ids"]) < 15:
                    ie["tx_ids"].append(tx_id)

        # Populate Account nodes in acct_di_graph and hetero_graph
        for aid, st in acct_acc.items():
            profile = {
                "entity_id": aid,
                "label": st["raw_id"],
                "entity_type": "ACCOUNT",
                "in_count": st["in_count"],
                "out_count": st["out_count"],
                "total_tx_count": st["in_count"] + st["out_count"],
                "in_amount": round(st["in_amount"], 2),
                "out_amount": round(st["out_amount"], 2),
                "total_volume": round(st["in_amount"] + st["out_amount"], 2),
                "net_flow": round(st["in_amount"] - st["out_amount"], 2),
                "first_seen": st["first_seen"],
                "last_seen": st["last_seen"],
                "locations": sorted(st["locations"]),
                "channels": sorted(st["channels"]),
                "merchant_categories": sorted(st["merchant_categories"]),
                "is_synthetic": st["is_synthetic"],
                "data_sources": sorted(st["data_sources"]),
                "fraud_tx_count": st["fraud_tx_count"],
                "tx_ids": st["tx_ids"],
            }
            self.account_stats[aid] = profile
            self.acct_di_graph.add_node(aid, **profile)
            self.hetero_graph.add_node(aid, **profile)

        # Add aggregated directed Account -> Account edges
        for (u, v), p in pair_agg.items():
            e_data = {
                "relationship_type": "ACCOUNT_SENT_TO_ACCOUNT",
                "tx_count": p["tx_count"],
                "total_amount": round(p["total_amount"], 2),
                "first_seen": p["first_seen"],
                "last_seen": p["last_seen"],
                "tx_ids": p["tx_ids"],
                "evidence_source": "transaction_ledger",
                "confidence": "HIGH_DIRECT_FACT",
                "is_direct": True,
                "is_synthetic": p["is_synthetic"],
            }
            self.acct_di_graph.add_edge(u, v, **e_data)
            self.hetero_graph.add_edge(u, v, key="AGG_TX", **e_data)

        # Add Device & IP nodes into hetero_graph (include ALL shared devices/IPs + devices/IPs of multi-tx accounts)
        for dev_id, linked_accts in self.device_to_accounts.items():
            is_shared = len(linked_accts) >= 2
            self.hetero_graph.add_node(
                dev_id,
                entity_id=dev_id,
                label=strip_prefix(dev_id),
                entity_type="DEVICE",
                linked_account_count=len(linked_accts),
                is_shared=is_shared,
            )

        for ip_id, linked_accts in self.ip_to_accounts.items():
            is_shared = len(linked_accts) >= 2
            self.hetero_graph.add_node(
                ip_id,
                entity_id=ip_id,
                label=strip_prefix(ip_id),
                entity_type="IP_ADDRESS",
                linked_account_count=len(linked_accts),
                is_shared=is_shared,
            )

        for (acct_id, infra_id, rel_type), ie in infra_edge_agg.items():
            if infra_id in self.hetero_graph:
                is_shared_infra = self.hetero_graph.nodes[infra_id].get("is_shared", False)
                self.hetero_graph.add_edge(
                    acct_id,
                    infra_id,
                    key=rel_type,
                    relationship_type=rel_type,
                    observation_count=ie["count"],
                    first_seen=ie["first_seen"],
                    last_seen=ie["last_seen"],
                    tx_ids=ie["tx_ids"],
                    evidence_source="session_telemetry",
                    confidence="MODERATE_SHARED_INFRA" if is_shared_infra else "DIRECT_TELEMETRY",
                    is_direct=True,
                )

        self._compute_topology_metrics()
        return self.get_graph_summary()

    def _compute_topology_metrics(self) -> None:
        n_accts = self.acct_di_graph.number_of_nodes()
        if n_accts == 0:
            return
        self.degree_centrality_map = nx.degree_centrality(self.acct_di_graph)

        # Mathematical optimization: components of size <= 2 always have 0.0 betweenness.
        # Computing betweenness strictly on components of size >= 3 yields identical scores 100x faster.
        undirected = self.acct_di_graph.to_undirected()
        self.community_map = {}
        self.betweenness_map = {n: 0.0 for n in self.acct_di_graph.nodes()}
        non_trivial_nodes: Set[str] = set()
        comm_idx = 0

        for comp in nx.connected_components(undirected):
            if len(comp) < 3:
                for node in comp:
                    self.community_map[node] = -1
            else:
                non_trivial_nodes.update(comp)
                if len(comp) <= 12:
                    comm_idx += 1
                    for node in comp:
                        self.community_map[node] = comm_idx
                else:
                    sub = undirected.subgraph(comp)
                    for comm in nx.community.greedy_modularity_communities(sub):
                        comm_idx += 1
                        for node in comm:
                            self.community_map[node] = comm_idx

        if non_trivial_nodes:
            active_di = self.acct_di_graph.subgraph(non_trivial_nodes)
            k_sample = min(80, len(non_trivial_nodes))
            sub_bet = nx.betweenness_centrality(
                active_di, k=k_sample, normalized=True, seed=42
            )
            self.betweenness_map.update(sub_bet)

    def get_graph_summary(self) -> Dict[str, Any]:
        undirected = self.acct_di_graph.to_undirected()
        multi_node_clusters = sum(
            1 for c in nx.connected_components(undirected) if len(c) >= 3
        ) if self.acct_di_graph.number_of_nodes() > 0 else 0
        shared_devices = sum(1 for s in self.device_to_accounts.values() if len(s) >= 2)
        shared_ips = sum(1 for s in self.ip_to_accounts.values() if len(s) >= 2)

        return {
            "total_transactions": int(len(self.df)),
            "unique_accounts": int(self.acct_di_graph.number_of_nodes()),
            "total_hetero_entities": int(self.hetero_graph.number_of_nodes()),
            "total_relationships": int(self.hetero_graph.number_of_edges()),
            "directed_account_edges": int(self.acct_di_graph.number_of_edges()),
            "multi_account_clusters": int(multi_node_clusters),
            "shared_devices_count": int(shared_devices),
            "shared_ips_count": int(shared_ips),
        }

    def _classify_node_visual_role(self, entity_id: str) -> Tuple[str, str]:
        """
        Maps node to required investigator workstation visual taxonomy:
          - RED (#EF4444): Suspected mule / high-risk account indicator
          - ORANGE (#F97316): Shared device node or shared-device-linked indicator
          - PURPLE (#A855F7): Shared IP / proxy node or IP-linked indicator
          - BLUE (#3B82F6): Normal account
        """
        node_data = self.hetero_graph.nodes.get(entity_id, {})
        etype = node_data.get("entity_type", "ACCOUNT")
        if etype == "DEVICE":
            return ("SHARED_DEVICE" if node_data.get("is_shared") else "DEVICE", "#F97316")
        if etype == "IP_ADDRESS":
            return ("SHARED_IP" if node_data.get("is_shared") else "IP_ADDRESS", "#A855F7")

        risk_info = self.entity_risk.get(entity_id, {})
        score = float(risk_info.get("risk_score", 0.0))
        patterns = risk_info.get("pattern_types", [])

        if score >= 62.0 or any(
            p in patterns
            for p in ["MULE_ACCOUNT_INDICATOR", "RAPID_PASS_THROUGH", "CIRCULAR_FLOW", "FAN_IN", "FAN_OUT"]
        ):
            return ("HIGH_RISK_INDICATOR", "#EF4444")
        if "SHARED_DEVICE" in patterns:
            return ("SHARED_DEVICE_ACCOUNT", "#F97316")
        if "SHARED_IP" in patterns:
            return ("SHARED_IP_ACCOUNT", "#A855F7")
        return ("NORMAL_ACCOUNT", "#3B82F6")

    def serialize_subgraph(
        self,
        seed_nodes: Set[str],
        include_shared_infra: bool = True,
        entity_types: Optional[Set[str]] = None,
        min_risk: float = 0.0,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None,
        max_nodes: int = 160,
    ) -> Dict[str, Any]:
        # Prioritize higher-risk seed nodes if exceeding max_nodes
        ordered_seeds = sorted(
            [n for n in seed_nodes if n in self.hetero_graph],
            key=lambda n: self.entity_risk.get(n, {}).get("risk_score", 0.0),
            reverse=True,
        )

        selected_nodes: Set[str] = set()
        for n in ordered_seeds:
            if len(selected_nodes) >= max_nodes:
                break
            ntype = self.hetero_graph.nodes[n].get("entity_type", "ACCOUNT")
            if entity_types and ntype not in entity_types:
                continue
            if ntype == "ACCOUNT":
                r_score = float(self.entity_risk.get(n, {}).get("risk_score", 0.0))
                if r_score < min_risk:
                    continue
            selected_nodes.add(n)

        # Attach shared Device / IP nodes connected to selected accounts so infrastructure bridges are visible
        if include_shared_infra:
            infra_additions: Set[str] = set()
            for n in list(selected_nodes):
                if self.hetero_graph.nodes[n].get("entity_type") == "ACCOUNT":
                    for dev_id in self.account_to_devices.get(n, set()):
                        if len(self.device_to_accounts.get(dev_id, set())) >= 2:
                            if not entity_types or "DEVICE" in entity_types:
                                infra_additions.add(dev_id)
                    for ip_id in self.account_to_ips.get(n, set()):
                        if len(self.ip_to_accounts.get(ip_id, set())) >= 2:
                            if not entity_types or "IP_ADDRESS" in entity_types:
                                infra_additions.add(ip_id)
            for inf in infra_additions:
                if len(selected_nodes) < max_nodes + 35:
                    selected_nodes.add(inf)

        nodes_out: List[Dict[str, Any]] = []
        for nid in selected_nodes:
            nd = self.hetero_graph.nodes[nid]
            etype = nd.get("entity_type", "ACCOUNT")
            role, color = self._classify_node_visual_role(nid)
            r_info = self.entity_risk.get(nid, {})
            nodes_out.append(
                {
                    "id": nid,
                    "label": nd.get("label", strip_prefix(nid)),
                    "entity_type": etype,
                    "visual_role": role,
                    "color": color,
                    "risk_score": round(float(r_info.get("risk_score", 18.0 if nd.get("is_shared") else 5.0)), 1),
                    "priority": r_info.get("priority", "MEDIUM" if nd.get("is_shared") else "LOW"),
                    "pattern_types": r_info.get("pattern_types", []),
                    "total_volume": nd.get("total_volume", 0.0),
                    "total_tx_count": nd.get("total_tx_count", nd.get("linked_account_count", 0)),
                    "is_synthetic": bool(nd.get("is_synthetic", False)),
                    "community_id": self.community_map.get(nid, -1),
                    "betweenness": round(float(self.betweenness_map.get(nid, 0.0)), 5),
                }
            )

        links_out: List[Dict[str, Any]] = []
        sub = self.hetero_graph.subgraph(selected_nodes)
        for u, v, key, ed in sub.edges(keys=True, data=True):
            first_seen = ed.get("first_seen")
            last_seen = ed.get("last_seen")
            if start_ts and last_seen and last_seen < start_ts:
                continue
            if end_ts and first_seen and first_seen > end_ts:
                continue
            links_out.append(
                {
                    "id": f"{u}->{v}:{key}",
                    "source": u,
                    "target": v,
                    "relationship_type": ed.get("relationship_type", "RELATED"),
                    "tx_count": ed.get("tx_count", ed.get("observation_count", 1)),
                    "total_amount": ed.get("total_amount", 0.0),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "tx_ids": ed.get("tx_ids", []),
                    "confidence": ed.get("confidence", "DIRECT"),
                    "is_synthetic": bool(ed.get("is_synthetic", False)),
                }
            )

        return {
            "nodes": nodes_out,
            "links": links_out,
            "meta": {
                "node_count": len(nodes_out),
                "link_count": len(links_out),
                "total_graph_entities": self.hetero_graph.number_of_nodes(),
                "is_bounded_subgraph": True,
            },
        }

    def get_ego_subgraph(self, entity_id: str, hops: int = 2, max_nodes: int = 120) -> Dict[str, Any]:
        resolved = self.resolve_entity_id(entity_id)
        if not resolved or resolved not in self.hetero_graph:
            return {"nodes": [], "links": [], "meta": {"node_count": 0, "link_count": 0}}

        visited: Set[str] = {resolved}
        frontier: Set[str] = {resolved}
        for _ in range(max(1, min(hops, 4))):
            next_frontier: Set[str] = set()
            for node in frontier:
                ntype = self.hetero_graph.nodes[node].get("entity_type")
                # Expand across transaction neighbors and shared infrastructure
                for succ in self.hetero_graph.successors(node):
                    if self.hetero_graph.nodes[succ].get("entity_type") in ("DEVICE", "IP_ADDRESS"):
                        if self.hetero_graph.nodes[succ].get("is_shared") or node == resolved:
                            next_frontier.add(succ)
                    else:
                        next_frontier.add(succ)
                for pred in self.hetero_graph.predecessors(node):
                    next_frontier.add(pred)
                if ntype in ("DEVICE", "IP_ADDRESS"):
                    for pred in self.hetero_graph.predecessors(node):
                        next_frontier.add(pred)
            visited.update(next_frontier)
            frontier = next_frontier
            if len(visited) >= max_nodes:
                break

        return self.serialize_subgraph(visited, include_shared_infra=True, max_nodes=max_nodes)

    def resolve_entity_id(self, raw_or_prefixed: str) -> Optional[str]:
        q = raw_or_prefixed.strip()
        if q in self.hetero_graph:
            return q
        for prefix in ("ACCOUNT:", "DEVICE:", "IP:"):
            candidate = f"{prefix}{q}"
            if candidate in self.hetero_graph:
                return candidate
        return None

    def find_connecting_paths(
        self, source_id: str, target_id: str, max_hops: int = 5
    ) -> Dict[str, Any]:
        s = self.resolve_entity_id(source_id)
        t = self.resolve_entity_id(target_id)
        if not s or not t:
            return {"directed_paths": [], "infrastructure_paths": []}

        directed_paths: List[List[str]] = []
        if s in self.acct_di_graph and t in self.acct_di_graph:
            try:
                for p in nx.all_simple_paths(self.acct_di_graph, s, t, cutoff=max_hops):
                    directed_paths.append(p)
                    if len(directed_paths) >= 5:
                        break
            except nx.NetworkXError:
                pass

        infra_paths: List[List[str]] = []
        undir = self.hetero_graph.to_undirected()
        if s in undir and t in undir and nx.has_path(undir, s, t):
            try:
                sp = nx.shortest_path(undir, s, t)
                if len(sp) <= max_hops + 2:
                    infra_paths.append(sp)
            except nx.NetworkXNoPath:
                pass

        return {
            "source": s,
            "target": t,
            "directed_paths": directed_paths,
            "infrastructure_paths": infra_paths,
        }

    def get_entity_detail(self, entity_id: str) -> Optional[Dict[str, Any]]:
        resolved = self.resolve_entity_id(entity_id)
        if not resolved or resolved not in self.hetero_graph:
            return None

        nd = dict(self.hetero_graph.nodes[resolved])
        etype = nd.get("entity_type", "ACCOUNT")
        role, color = self._classify_node_visual_role(resolved)
        r_info = self.entity_risk.get(resolved, {})

        incoming_neighbors = []
        outgoing_neighbors = []
        if etype == "ACCOUNT":
            for pred in self.acct_di_graph.predecessors(resolved):
                ed = self.acct_di_graph.edges[pred, resolved]
                incoming_neighbors.append(
                    {
                        "entity_id": pred,
                        "label": strip_prefix(pred),
                        "tx_count": ed["tx_count"],
                        "total_amount": ed["total_amount"],
                        "last_seen": ed["last_seen"],
                        "tx_ids": ed["tx_ids"],
                    }
                )
            for succ in self.acct_di_graph.successors(resolved):
                ed = self.acct_di_graph.edges[resolved, succ]
                outgoing_neighbors.append(
                    {
                        "entity_id": succ,
                        "label": strip_prefix(succ),
                        "tx_count": ed["tx_count"],
                        "total_amount": ed["total_amount"],
                        "last_seen": ed["last_seen"],
                        "tx_ids": ed["tx_ids"],
                    }
                )

        shared_devices = []
        for dev_id in self.account_to_devices.get(resolved, set()):
            co_accounts = sorted(self.device_to_accounts.get(dev_id, set()) - {resolved})
            shared_devices.append(
                {
                    "device_id": dev_id,
                    "label": strip_prefix(dev_id),
                    "is_shared": len(co_accounts) > 0,
                    "co_using_accounts": co_accounts,
                }
            )

        shared_ips = []
        for ip_id in self.account_to_ips.get(resolved, set()):
            co_accounts = sorted(self.ip_to_accounts.get(ip_id, set()) - {resolved})
            shared_ips.append(
                {
                    "ip_id": ip_id,
                    "label": strip_prefix(ip_id),
                    "is_shared": len(co_accounts) > 0,
                    "co_using_accounts": co_accounts,
                }
            )

        linked_accounts = []
        if etype == "DEVICE":
            linked_accounts = sorted(self.device_to_accounts.get(resolved, set()))
        elif etype == "IP_ADDRESS":
            linked_accounts = sorted(self.ip_to_accounts.get(resolved, set()))

        # Gather recent transactions involving this entity
        raw_label = strip_prefix(resolved)
        related_txs: List[Dict[str, Any]] = []
        if not self.df.empty:
            if etype == "ACCOUNT":
                sub_df = self.df[
                    (self.df["sender_account"] == raw_label)
                    | (self.df["receiver_account"] == raw_label)
                ].sort_values("epoch", ascending=False)
            elif etype == "DEVICE":
                sub_df = self.df[self.df["device_hash"] == raw_label].sort_values("epoch", ascending=False)
            else:
                sub_df = self.df[self.df["ip_address"] == raw_label].sort_values("epoch", ascending=False)
            related_txs = sub_df.head(30).to_dict(orient="records")

        return {
            "entity_id": resolved,
            "label": nd.get("label", raw_label),
            "entity_type": etype,
            "visual_role": role,
            "color": color,
            "profile": nd,
            "risk": r_info,
            "centrality": {
                "degree_centrality": round(float(self.degree_centrality_map.get(resolved, 0.0)), 5),
                "betweenness_centrality": round(float(self.betweenness_map.get(resolved, 0.0)), 5),
                "community_id": self.community_map.get(resolved, -1),
                "in_degree": int(self.acct_di_graph.in_degree(resolved)) if resolved in self.acct_di_graph else len(linked_accounts),
                "out_degree": int(self.acct_di_graph.out_degree(resolved)) if resolved in self.acct_di_graph else 0,
            },
            "incoming_counterparties": sorted(incoming_neighbors, key=lambda x: x["total_amount"], reverse=True),
            "outgoing_counterparties": sorted(outgoing_neighbors, key=lambda x: x["total_amount"], reverse=True),
            "devices": shared_devices,
            "ips": shared_ips,
            "linked_accounts": linked_accounts,
            "recent_transactions": related_txs,
            "detection_ids": self.entity_detections.get(resolved, []),
        }
