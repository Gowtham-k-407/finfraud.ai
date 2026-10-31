import type {
  CaseRecord,
  EntityDetail,
  GraphPayload,
  InvestigationReport,
  PatternDetection,
  TransactionRecord,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      errDetail = data.detail || errDetail;
    } catch {
      // ignore json parse failure
    }
    throw new Error(errDetail);
  }
  return res.json();
}

export const api = {
  getHealth: () => request<any>('/health'),
  getOverview: () => request<any>('/overview'),
  getDatasetStatus: () => request<any>('/datasets/status'),
  getModelsStatus: () => request<any>('/models/status'),

  reprocessDataset: (payload: {
    source_mode: string;
    max_kaggle_rows: number;
    include_synthetic_scenarios: boolean;
  }) =>
    request<any>('/datasets/process', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  uploadCsvDataset: (file: File, includeSynthetic: boolean, maxRows: number) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('include_synthetic_scenarios', String(includeSynthetic));
    formData.append('max_rows', String(maxRows));
    return request<any>('/datasets/upload', {
      method: 'POST',
      body: formData,
    });
  },

  getSubgraph: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '' && v !== null) {
        qs.set(k, String(v));
      }
    });
    return request<GraphPayload>(`/graph/subgraph?${qs.toString()}`);
  },

  getEgoGraph: (entityId: string, hops = 2, maxNodes = 120) =>
    request<GraphPayload>(
      `/graph/ego/${encodeURIComponent(entityId)}?hops=${hops}&max_nodes=${maxNodes}`
    ),

  findPaths: (source: string, target: string, maxHops = 5) =>
    request<{
      source: string;
      target: string;
      directed_paths: string[][];
      infrastructure_paths: string[][];
    }>(
      `/graph/paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&max_hops=${maxHops}`
    ),

  getEntityDetail: (entityId: string) =>
    request<EntityDetail>(`/entities/${encodeURIComponent(entityId)}`),

  listEntities: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.set(k, String(v));
    });
    return request<{ total: number; items: any[] }>(`/entities?${qs.toString()}`);
  },

  listTransactions: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.set(k, String(v));
    });
    return request<{
      total: number;
      page: number;
      page_size: number;
      items: TransactionRecord[];
    }>(`/transactions?${qs.toString()}`);
  },

  getTransactionDetail: (txId: string) =>
    request<{
      transaction: TransactionRecord;
      sender_risk: any;
      receiver_risk: any;
      related_detections: PatternDetection[];
    }>(`/transactions/${encodeURIComponent(txId)}`),

  listDetections: (params?: Record<string, string | undefined>) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v) qs.set(k, v);
      });
    }
    return request<{ total: number; items: PatternDetection[] }>(`/detections?${qs.toString()}`);
  },

  runInvestigation: (targetId: string, targetType = 'ACCOUNT', useLlm = true) =>
    request<InvestigationReport>('/investigations', {
      method: 'POST',
      body: JSON.stringify({
        target_id: targetId,
        target_type: targetType,
        use_llm_if_available: useLlm,
      }),
    }),

  listInvestigations: () =>
    request<{ total: number; items: any[] }>('/investigations'),

  getInvestigation: (id: string) =>
    request<InvestigationReport>(`/investigations/${encodeURIComponent(id)}`),

  addInvestigationNote: (
    id: string,
    payload: {
      author?: string;
      content: string;
      hypothesis_id?: string;
      verdict?: 'USEFUL' | 'REJECTED';
    }
  ) =>
    request<InvestigationReport>(`/investigations/${encodeURIComponent(id)}/notes`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listCases: () => request<{ total: number; items: CaseRecord[] }>('/cases'),

  getCase: (caseId: string) => request<CaseRecord>(`/cases/${encodeURIComponent(caseId)}`),

  createCase: (payload: {
    title: string;
    primary_entity: string;
    priority: string;
    assigned_analyst?: string;
    investigation_id?: string;
    detection_ids?: string[];
    summary: string;
  }) =>
    request<CaseRecord>('/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCase: (
    caseId: string,
    payload: { status?: string; priority?: string; assigned_analyst?: string; note?: string }
  ) =>
    request<CaseRecord>(`/cases/${encodeURIComponent(caseId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
};

