export interface GraphNode {
  id: string;
  label: string;
  entity_type: 'ACCOUNT' | 'DEVICE' | 'IP_ADDRESS' | string;
  visual_role: string;
  color: string;
  risk_score: number;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  pattern_types: string[];
  total_volume: number;
  total_tx_count: number;
  is_synthetic: boolean;
  community_id: number;
  betweenness: number;
  x?: number;
  y?: number;
}

export interface GraphLink {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  relationship_type: string;
  tx_count: number;
  total_amount: number;
  first_seen?: string;
  last_seen?: string;
  tx_ids: string[];
  confidence: string;
  is_synthetic: boolean;
}

export interface GraphPayload {
  nodes: GraphNode[];
  links: GraphLink[];
  meta: {
    node_count: number;
    link_count: number;
    total_graph_entities?: number;
    is_bounded_subgraph?: boolean;
  };
}

export interface PatternDetection {
  detection_id: string;
  pattern_type: string;
  pattern_label: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  primary_entity: string;
  involved_entities: string[];
  supporting_transactions: string[];
  total_amount: number;
  time_window_start?: string;
  time_window_end?: string;
  duration_minutes?: number;
  summary: string;
  explanation: string;
  alternative_explanations: string[];
  confidence_basis: string;
  data_source: string;
  is_synthetic_scenario: boolean;
  scenario_tag?: string;
  metrics: Record<string, any>;
}

export interface TransactionRecord {
  transaction_id: string;
  timestamp: string;
  sender_account: string;
  receiver_account: string;
  amount: number;
  transaction_type: string;
  merchant_category: string;
  location: string;
  device_used: string;
  is_fraud: boolean;
  fraud_type: string;
  spending_deviation_score: number;
  velocity_score: number;
  geo_anomaly_score: number;
  payment_channel: string;
  ip_address: string;
  device_hash: string;
  is_synthetic: boolean;
  data_source: string;
  scenario_tag: string;
  ml_anomaly_score?: number;
  ml_is_anomaly?: boolean;
}

export interface RiskContribution {
  factor: string;
  raw_score: number;
  weight: number;
  weighted_points: number;
  detail: string;
}

export interface EntityDetail {
  entity_id: string;
  label: string;
  entity_type: string;
  visual_role: string;
  color: string;
  profile: Record<string, any>;
  risk: {
    risk_score?: number;
    priority?: string;
    ml_anomaly_score?: number;
    pattern_types?: string[];
    detection_count?: number;
    evidence_quality?: string;
    model_version?: string;
    contributions?: RiskContribution[];
  };
  centrality: {
    degree_centrality: number;
    betweenness_centrality: number;
    community_id: number;
    in_degree: number;
    out_degree: number;
  };
  incoming_counterparties: Array<{
    entity_id: string;
    label: string;
    tx_count: number;
    total_amount: number;
    last_seen: string;
    tx_ids: string[];
  }>;
  outgoing_counterparties: Array<{
    entity_id: string;
    label: string;
    tx_count: number;
    total_amount: number;
    last_seen: string;
    tx_ids: string[];
  }>;
  devices: Array<{
    device_id: string;
    label: string;
    is_shared: boolean;
    co_using_accounts: string[];
  }>;
  ips: Array<{
    ip_id: string;
    label: string;
    is_shared: boolean;
    co_using_accounts: string[];
  }>;
  linked_accounts: string[];
  recent_transactions: TransactionRecord[];
  detections?: PatternDetection[];
}

export interface EvidenceItem {
  evidence_id: string;
  category: string;
  title: string;
  description: string;
  is_direct_fact: boolean;
  confidence: string;
  related_entities: string[];
  supporting_transactions: string[];
  timestamp?: string;
  amount?: number;
  metadata?: Record<string, any>;
}

export interface HypothesisEvaluation {
  hypothesis_id: string;
  title: string;
  category: 'SUSPICIOUS_TYPOLOGY' | 'BENIGN_ALTERNATIVE' | string;
  description: string;
  confidence: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  missing_evidence: string[];
  recommended_next_step: string;
  analyst_verdict?: 'USEFUL' | 'REJECTED' | null;
}

export interface InvestigationReport {
  investigation_id: string;
  target_id: string;
  target_type: string;
  created_at: string;
  generation_mode: string;
  llm_provider?: string | null;
  overall_priority: string;
  composite_risk_score: number;
  executive_summary: string;
  involved_entities: string[];
  suspicious_paths: string[][];
  supporting_transactions: string[];
  total_volume_analyzed: number;
  currency: string;
  time_span: { start?: string | null; end?: string | null };
  verified_facts: EvidenceItem[];
  analytical_inferences: string[];
  hypotheses: HypothesisEvaluation[];
  alternative_explanations: string[];
  evidence_limitations: string[];
  recommended_actions: string[];
  data_provenance_note: string;
  notes: Array<{
    note_id: string;
    author: string;
    content: string;
    hypothesis_id?: string;
    verdict?: string;
    created_at: string;
  }>;
}

export interface CaseRecord {
  case_id: string;
  title: string;
  primary_entity: string;
  status: 'OPEN' | 'IN_REVIEW' | 'ESCALATED' | 'CLOSED_BENIGN' | string;
  priority: string;
  assigned_analyst: string;
  investigation_id?: string;
  detection_ids: string[];
  summary: string;
  created_at: string;
  updated_at: string;
  timeline?: Array<{
    event_id: string;
    actor: string;
    action: string;
    detail: string;
    created_at: string;
  }>;
}

