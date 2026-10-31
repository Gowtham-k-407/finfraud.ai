import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileSearch,
  GitBranch,
  Globe,
  Search,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import type { PatternDetection, TransactionRecord } from '../types/api';
import {
  formatTimestamp,
  formatUSD,
  PatternBadge,
  ProvenanceBadge,
  SeverityBadge,
} from '../components/Badge';

export const TransactionIntelligencePage: React.FC = () => {
  const navigate = useNavigate();

  const [items, setItems] = useState<TransactionRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 35;

  const [search, setSearch] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [anomaliesOnly, setAnomaliesOnly] = useState(false);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  // Selected transaction detail drawer
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null);
  const [txDetail, setTxDetail] = useState<{
    transaction: TransactionRecord;
    sender_risk: any;
    receiver_risk: any;
    related_detections: PatternDetection[];
  } | null>(null);

  const fetchTransactions = () => {
    setLoading(true);
    api
      .listTransactions({
        search: search.trim() || undefined,
        min_amount: minAmount ? Number(minAmount) : undefined,
        anomalies_only: anomaliesOnly,
        data_source_filter: sourceFilter,
        page,
        page_size: pageSize,
      })
      .then((res) => {
        setItems(res.items || []);
        setTotal(res.total || 0);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, anomaliesOnly, sourceFilter]);

  useEffect(() => {
    if (!selectedTxId) {
      setTxDetail(null);
      return;
    }
    api
      .getTransactionDetail(selectedTxId)
      .then(setTxDetail)
      .catch(() => setTxDetail(null));
  }, [selectedTxId]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex flex-col lg:flex-row">
      {/* Main Ledger Table Section */}
      <div className="flex-1 p-4 lg:p-6 space-y-4 min-w-0">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold tracking-tight flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" />
              <span>Transaction Intelligence & Anomaly Ledger</span>
            </h1>
            <p className="text-xs text-slate-500">
              Ranked by Isolation Forest behavioral anomaly score · {total.toLocaleString()}{' '}
              matching records
            </p>
          </div>

          {/* Filter Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              fetchTransactions();
            }}
            className="flex flex-wrap items-center gap-2 text-xs"
          >
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="TX ID, Account, Device, IP..."
                className="w-52 pl-8 pr-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700 font-mono text-xs"
              />
            </div>

            <input
              type="number"
              value={minAmount}
              onChange={(e) => setMinAmount(e.target.value)}
              placeholder="Min USD"
              className="w-24 px-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700 font-mono text-xs"
            />

            <select
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter transactions by data source"
              className="px-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700 text-xs"
            >
              <option value="all">All Provenance</option>
              <option value="real_only">Real Kaggle Dataset Only</option>
              <option value="synthetic_only">Synthetic Scenarios Only</option>
            </select>

            <label className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={anomaliesOnly}
                onChange={(e) => {
                  setAnomaliesOnly(e.target.checked);
                  setPage(1);
                }}
                className="accent-red-500"
              />
              <span>Anomalies Only</span>
            </label>

            <button
              type="submit"
              className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium"
            >
              Search
            </button>
          </form>
        </div>

        {/* Dense Financial Ledger Table */}
        <div className="rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] font-mono uppercase text-slate-500 bg-slate-50/80 dark:bg-slate-900/50">
                  <th className="py-2.5 px-3">TX ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Sender → Receiver</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3">Channel / Location</th>
                  <th className="py-2.5 px-3">Device / IP</th>
                  <th className="py-2.5 px-3">IForest Score</th>
                  <th className="py-2.5 px-3">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800/70 text-xs">
                {loading ? (
                  Array.from({ length: 8 }).map((_, idx) => (
                    <tr key={idx}>
                      <td colSpan={8} className="p-3">
                        <div className="h-5 rounded bg-slate-100 dark:bg-slate-800/60 animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-500">
                      No transactions matched your filter criteria.
                    </td>
                  </tr>
                ) : (
                  items.map((tx) => {
                    const anomScore = tx.ml_anomaly_score ?? 0;
                    const isSelected = selectedTxId === tx.transaction_id;
                    return (
                      <tr
                        key={tx.transaction_id}
                        onClick={() => setSelectedTxId(tx.transaction_id)}
                        className={clsx(
                          'cursor-pointer transition-colors',
                          isSelected
                            ? 'bg-blue-600/15'
                            : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                        )}
                      >
                        <td className="py-2 px-3 font-mono font-semibold whitespace-nowrap">
                          {tx.transaction_id}
                        </td>
                        <td className="py-2 px-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                          {formatTimestamp(tx.timestamp)}
                        </td>
                        <td className="py-2 px-3 font-mono whitespace-nowrap">
                          <span className="text-blue-600 dark:text-blue-400">
                            {tx.sender_account}
                          </span>
                          <span className="mx-1.5 text-slate-400">→</span>
                          <span className="text-orange-500 dark:text-orange-300">
                            {tx.receiver_account}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-mono font-semibold whitespace-nowrap">
                          {formatUSD(tx.amount)}
                        </td>
                        <td className="py-2 px-3 text-[11px] whitespace-nowrap">
                          {tx.payment_channel} · {tx.location}
                        </td>
                        <td className="py-2 px-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                          {tx.device_hash || '—'} / {tx.ip_address || '—'}
                        </td>
                        <td className="py-2 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span
                              className={clsx(
                                'font-mono font-bold',
                                anomScore >= 75
                                  ? 'text-red-500'
                                  : anomScore >= 50
                                  ? 'text-orange-400'
                                  : 'text-slate-500'
                              )}
                            >
                              {anomScore.toFixed(1)}
                            </span>
                            <div className="w-14 h-1.5 rounded bg-slate-200 dark:bg-slate-800 overflow-hidden">
                              <div
                                className={clsx(
                                  'h-full',
                                  anomScore >= 75
                                    ? 'bg-red-500'
                                    : anomScore >= 50
                                    ? 'bg-orange-400'
                                    : 'bg-blue-500'
                                )}
                                style={{ width: `${Math.min(100, anomScore)}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="py-2 px-3 whitespace-nowrap">
                          <ProvenanceBadge
                            isSynthetic={tx.is_synthetic}
                            source={tx.data_source}
                          />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="px-4 py-2.5 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-500 font-mono">
              Page {page} of {totalPages} ({total.toLocaleString()} records)
            </span>
            <div className="flex items-center gap-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="p-1.5 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Slide-in Transaction Evidence Drawer */}
      {selectedTxId && txDetail && (
        <aside className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] p-4 space-y-4 overflow-y-auto">
          <div className="flex items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase text-slate-500">
                  TRANSACTION EVIDENCE
                </span>
                <ProvenanceBadge
                  isSynthetic={txDetail.transaction.is_synthetic}
                  source={txDetail.transaction.data_source}
                />
              </div>
              <h2 className="font-mono text-base font-bold mt-1">
                {txDetail.transaction.transaction_id}
              </h2>
            </div>
            <button
              onClick={() => setSelectedTxId(null)}
              className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-3 rounded bg-slate-50 dark:bg-[#131C2E] border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Transfer Amount</span>
              <span className="font-mono text-base font-bold">
                {formatUSD(txDetail.transaction.amount)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Timestamp</span>
              <span className="font-mono">{formatTimestamp(txDetail.transaction.timestamp)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">IForest Anomaly Score</span>
              <span className="font-mono font-bold text-red-400">
                {txDetail.transaction.ml_anomaly_score ?? 0} / 100
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Velocity / Geo Anomaly</span>
              <span className="font-mono">
                {txDetail.transaction.velocity_score} / {txDetail.transaction.geo_anomaly_score}
              </span>
            </div>
          </div>

          {/* Sender -> Receiver Relationship Cards */}
          <div className="space-y-2 text-xs">
            <div className="text-[11px] font-semibold uppercase text-slate-500">
              Counterparty Risk Context
            </div>
            <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[10px] text-slate-500">SENDER</div>
                <div className="font-mono font-semibold text-blue-500">
                  {txDetail.transaction.sender_account}
                </div>
              </div>
              <SeverityBadge severity={txDetail.sender_risk?.priority || 'LOW'} />
            </div>

            <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[10px] text-slate-500">RECEIVER</div>
                <div className="font-mono font-semibold text-orange-400">
                  {txDetail.transaction.receiver_account}
                </div>
              </div>
              <SeverityBadge severity={txDetail.receiver_risk?.priority || 'LOW'} />
            </div>
          </div>

          {/* Session Telemetry */}
          <div className="space-y-1.5 text-xs">
            <div className="text-[11px] font-semibold uppercase text-slate-500">
              Session Telemetry
            </div>
            <div className="p-2 rounded border border-slate-200 dark:border-slate-800 font-mono flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-orange-500" />
              <span>Device: {txDetail.transaction.device_hash || 'Not recorded'}</span>
            </div>
            <div className="p-2 rounded border border-slate-200 dark:border-slate-800 font-mono flex items-center gap-2">
              <Globe className="w-3.5 h-3.5 text-purple-400" />
              <span>IP: {txDetail.transaction.ip_address || 'Not recorded'}</span>
            </div>
          </div>

          {/* Related Network Detections */}
          {txDetail.related_detections.length > 0 && (
            <div className="space-y-2 text-xs">
              <div className="text-[11px] font-semibold uppercase text-slate-500">
                Associated Network Detections ({txDetail.related_detections.length})
              </div>
              {txDetail.related_detections.map((d) => (
                <div
                  key={d.detection_id}
                  className="p-2.5 rounded border border-red-500/25 bg-red-500/5 space-y-1"
                >
                  <PatternBadge type={d.pattern_type} />
                  <p className="text-[11px] text-slate-600 dark:text-slate-300">{d.summary}</p>
                </div>
              ))}
            </div>
          )}

          {/* Investigation Actions */}
          <div className="grid grid-cols-2 gap-2 pt-2">
            <button
              onClick={() =>
                navigate(
                  `/network?focus=${encodeURIComponent(
                    `ACCOUNT:${txDetail.transaction.sender_account}`
                  )}`
                )
              }
              className="py-2 px-2.5 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 text-xs font-medium inline-flex items-center justify-center gap-1.5"
            >
              <GitBranch className="w-3.5 h-3.5" />
              <span>View Network</span>
            </button>
            <button
              onClick={() =>
                navigate(
                  `/investigations?target=${encodeURIComponent(
                    `ACCOUNT:${txDetail.transaction.sender_account}`
                  )}&type=ACCOUNT`
                )
              }
              className="py-2 px-2.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium inline-flex items-center justify-center gap-1.5"
            >
              <FileSearch className="w-3.5 h-3.5" />
              <span>Investigate</span>
            </button>
          </div>
        </aside>
      )}
    </div>
  );
};

