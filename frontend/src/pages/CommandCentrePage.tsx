import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  GitBranch,
  Layers,
  Network,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';
import {
  formatShortEntity,
  formatUSD,
  PatternBadge,
  ProvenanceBadge,
  SeverityBadge,
} from '../components/Badge';
import type { PatternDetection } from '../types/api';

export const CommandCentrePage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadOverview = () => {
    setLoading(true);
    setError(null);
    api
      .getOverview()
      .then((res) => setData(res))
      .catch((err) => setError(err.message || 'Failed to load Command Centre metrics'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadOverview();
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse"
            />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 h-72 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse" />
          <div className="h-72 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8">
        <div className="max-w-lg p-5 rounded border border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-300 space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="w-5 h-5" />
            <span>Backend Telemetry Unavailable</span>
          </div>
          <p className="text-xs leading-relaxed">{error}</p>
          <button
            onClick={loadOverview}
            className="px-3 py-1.5 rounded bg-red-600 text-white text-xs font-medium hover:bg-red-500"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const { kpis, dataset_quality } = data;

  const metricCards = [
    {
      label: 'Transactions Analyzed',
      value: kpis.total_transactions?.toLocaleString() || '0',
      sub: `${dataset_quality?.real_dataset_rows?.toLocaleString() || 0} real / ${dataset_quality?.synthetic_scenario_rows || 0} scenario`,
    },
    {
      label: 'Unique Accounts',
      value: kpis.unique_accounts?.toLocaleString() || '0',
      sub: `${kpis.directed_account_edges?.toLocaleString() || 0} directed flow edges`,
    },
    {
      label: 'Graph Entities',
      value: kpis.total_hetero_entities?.toLocaleString() || '0',
      sub: `${kpis.shared_devices_count || 0} shared devices · ${kpis.shared_ips_count || 0} shared IPs`,
    },
    {
      label: 'Entities Requiring Review',
      value: kpis.suspicious_entities_review?.toLocaleString() || '0',
      sub: `${kpis.critical_entities || 0} critical priority indicators`,
      accent: 'text-red-500',
    },
    {
      label: 'Network Detections',
      value: kpis.total_detections?.toLocaleString() || '0',
      sub: `${kpis.multi_account_clusters || 0} multi-account components`,
      accent: 'text-orange-500',
    },
    {
      label: 'IForest ML Anomalies',
      value: kpis.ml_anomalous_transactions?.toLocaleString() || '0',
      sub: `${kpis.open_cases || 0} active FIU investigation cases`,
      accent: 'text-blue-500',
    },
  ];

  return (
    <div className="p-4 lg:p-6 space-y-5 max-w-[1600px] mx-auto">
      {/* Top Title & Dataset Provenance Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800/80">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
            Financial Crime Network Command Centre
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Active Source:{' '}
            <span className="font-mono text-slate-700 dark:text-slate-300">
              {dataset_quality?.source_description || 'Active Parquet Store'}
            </span>{' '}
            · Total Volume:{' '}
            <span className="font-mono text-slate-700 dark:text-slate-300">
              {formatUSD(dataset_quality?.total_volume_usd)}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => navigate('/network')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
          >
            <Network className="w-3.5 h-3.5" />
            <span>Open Network Explorer</span>
          </button>
          <button
            onClick={() => navigate('/data')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0F1623] hover:border-blue-500 text-xs font-medium"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Upload / Configure Dataset</span>
          </button>
          <button
            onClick={loadOverview}
            className="p-1.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0F1623] text-slate-500 hover:text-slate-900 dark:hover:text-white"
            title="Refresh telemetry"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {metricCards.map((m) => (
          <div
            key={m.label}
            className="p-3.5 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623]"
          >
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              {m.label}
            </div>
            <div
              className={`mt-1.5 text-2xl font-mono font-bold tracking-tight ${
                m.accent || 'text-slate-900 dark:text-white'
              }`}
            >
              {m.value}
            </div>
            <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 truncate">
              {m.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row: Temporal Activity + Pattern Typology Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623]">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                Transaction Activity & Unsupervised Anomaly Volume
              </h2>
              <p className="text-[11px] text-slate-500">
                Chronological ledger throughput and Isolation Forest behavioral outliers
              </p>
            </div>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.activity_timeline || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                <XAxis
                  dataKey="period"
                  tick={{ fontSize: 10, fill: '#94A3B8' }}
                  tickLine={false}
                />
                <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F1623',
                    borderColor: '#334155',
                    fontSize: '12px',
                    color: '#F8FAFC',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="tx_count"
                  name="Transactions"
                  stroke="#3B82F6"
                  fill="#3B82F6"
                  fillOpacity={0.16}
                />
                <Area
                  type="monotone"
                  dataKey="anomalies"
                  name="IForest Anomalies"
                  stroke="#EF4444"
                  fill="#EF4444"
                  fillOpacity={0.24}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623]">
          <div className="mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Detected Network Typologies
            </h2>
            <p className="text-[11px] text-slate-500">
              Structural & shared-infrastructure patterns requiring human review
            </p>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.pattern_breakdown || []}
                layout="vertical"
                margin={{ left: 10, right: 12 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#94A3B8' }} />
                <YAxis
                  type="category"
                  dataKey="pattern_type"
                  width={125}
                  tick={{ fontSize: 9, fill: '#94A3B8' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F1623',
                    borderColor: '#334155',
                    fontSize: '12px',
                    color: '#F8FAFC',
                  }}
                />
                <Bar dataKey="count" name="Detections" fill="#F97316" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Main Operational Split: Priority Suspicious Network Detections + High-Risk Entities */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Priority Network Detections Table */}
        <div className="xl:col-span-2 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-500" />
              <h2 className="text-xs font-semibold uppercase tracking-wider">
                Priority Suspicious Network & Relationship Detections
              </h2>
            </div>
            <button
              onClick={() => navigate('/investigations')}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
            >
              View All ({kpis.total_detections})
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] font-mono uppercase text-slate-500 bg-slate-50/70 dark:bg-slate-900/40">
                  <th className="py-2.5 px-3">Severity / Score</th>
                  <th className="py-2.5 px-3">Typology & Provenance</th>
                  <th className="py-2.5 px-3">Focal Entity & Summary</th>
                  <th className="py-2.5 px-3 text-right">Flow Volume</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800/70 text-xs">
                {(data.top_detections || []).map((det: PatternDetection) => (
                  <tr
                    key={det.detection_id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={det.severity} />
                        <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                          {det.risk_score}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <div className="flex flex-col gap-1 items-start">
                        <PatternBadge type={det.pattern_type} />
                        <ProvenanceBadge
                          isSynthetic={det.is_synthetic_scenario}
                          source={det.data_source}
                        />
                      </div>
                    </td>
                    <td className="py-2.5 px-3 max-w-md">
                      <div className="font-mono font-semibold text-slate-900 dark:text-white">
                        {formatShortEntity(det.primary_entity)}
                        <span className="ml-2 text-[11px] font-normal text-slate-500">
                          ({det.involved_entities.length} entities ·{' '}
                          {det.supporting_transactions.length} TXs)
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-2 mt-0.5">
                        {det.summary}
                      </p>
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono whitespace-nowrap">
                      {formatUSD(det.total_amount)}
                    </td>
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() =>
                            navigate(
                              `/network?focus=${encodeURIComponent(det.primary_entity)}`
                            )
                          }
                          className="px-2 py-1 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 text-[11px] font-medium inline-flex items-center gap-1"
                          title="Inspect ego network in Graph Explorer"
                        >
                          <GitBranch className="w-3 h-3" />
                          <span>Graph</span>
                        </button>
                        <button
                          onClick={() =>
                            navigate(
                              `/investigations?target=${encodeURIComponent(
                                det.primary_entity
                              )}&type=ACCOUNT`
                            )
                          }
                          className="px-2 py-1 rounded bg-blue-600/15 text-blue-600 dark:text-blue-400 border border-blue-500/30 hover:bg-blue-600 hover:text-white text-[11px] font-medium inline-flex items-center gap-1 transition-colors"
                          title="Generate evidence-backed investigation report"
                        >
                          <FileSearch className="w-3 h-3" />
                          <span>Investigate</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: High-Risk Accounts Queue & Active Cases */}
        <div className="space-y-4">
          <div className="rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider">
                Highest-Priority Accounts
              </h2>
              <span className="text-[11px] font-mono text-slate-500">Hybrid Score</span>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-slate-800/70">
              {(data.top_suspicious_entities || []).slice(0, 7).map((ent: any) => (
                <div
                  key={ent.entity_id}
                  className="px-4 py-2.5 flex items-center justify-between gap-2 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          navigate(`/network?focus=${encodeURIComponent(ent.entity_id)}`)
                        }
                        className="font-mono text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline truncate"
                      >
                        {ent.label}
                      </button>
                      <ProvenanceBadge isSynthetic={ent.is_synthetic} />
                    </div>
                    <div className="text-[11px] text-slate-500 truncate mt-0.5">
                      {ent.pattern_types.join(' · ') || 'Behavioral Anomaly'} ·{' '}
                      {formatUSD(ent.total_volume)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <SeverityBadge severity={ent.priority} />
                    <span className="font-mono text-xs font-bold w-8 text-right">
                      {ent.risk_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Active FIU Cases Summary */}
          <div className="rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider">
                Recent FIU Cases
              </h2>
              <button
                onClick={() => navigate('/cases')}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5"
              >
                <span>Audit Trail</span>
                <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-slate-800/70">
              {(data.recent_cases || []).map((c: any) => (
                <div
                  key={c.case_id}
                  onClick={() => navigate('/cases')}
                  className="px-4 py-2.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                      {c.case_id}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      {c.status}
                    </span>
                  </div>
                  <div className="text-xs font-medium mt-1 truncate">{c.title}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Assigned: {c.assigned_analyst}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

