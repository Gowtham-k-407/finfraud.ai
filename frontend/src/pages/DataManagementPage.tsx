import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Cpu,
  Database,
  FileUp,
  RefreshCw,
  ShieldCheck,
  Sliders,
} from 'lucide-react';
import { api } from '../services/api';
import { formatUSD } from '../components/Badge';

export const DataManagementPage: React.FC = () => {
  const [datasetInfo, setDatasetInfo] = useState<any>(null);
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reprocess form state
  const [sourceMode, setSourceMode] = useState('hybrid');
  const [maxRows, setMaxRows] = useState(6000);
  const [includeSynthetic, setIncludeSynthetic] = useState(true);

  // CSV Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadIncludeSyn, setUploadIncludeSyn] = useState(false);

  const loadHealth = async () => {
    setLoading(true);
    try {
      const [ds, ms] = await Promise.all([api.getDatasetStatus(), api.getModelsStatus()]);
      setDatasetInfo(ds);
      setModelInfo(ms);
      if (ds?.quality_report?.source_mode) {
        setSourceMode(ds.quality_report.source_mode);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const handleReprocess = async (e: React.FormEvent) => {
    e.preventDefault();
    setProcessing(true);
    setFeedback(null);
    setError(null);
    try {
      const res = await api.reprocessDataset({
        source_mode: sourceMode,
        max_kaggle_rows: maxRows,
        include_synthetic_scenarios: includeSynthetic,
      });
      setFeedback(
        `Pipeline rebuilt in ${res.quality_report.processing_time_seconds}s: ${res.quality_report.active_rows_loaded.toLocaleString()} records indexed, ${res.detections_found} network detections discovered.`
      );
      await loadHealth();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleUploadCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setProcessing(true);
    setFeedback(null);
    setError(null);
    try {
      const res = await api.uploadCsvDataset(uploadFile, uploadIncludeSyn, 25000);
      setFeedback(
        `Uploaded '${uploadFile.name}': ${res.quality_report.active_rows_loaded.toLocaleString()} valid transactions processed (${res.detections_found} patterns detected).`
      );
      setUploadFile(null);
      await loadHealth();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const qr = datasetInfo?.quality_report || {};
  const iforest = modelInfo?.isolation_forest || {};
  const evalData = iforest.evaluation || {};

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-5">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
        <h1 className="text-lg font-semibold tracking-tight flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-500" />
          <span>Dataset Ingestion, Provenance & ML Model Health</span>
        </h1>
        <p className="text-xs text-slate-500">
          Chunked Pandas validation, Parquet analytical store, CSV upload, and Isolation Forest diagnostics
        </p>
      </div>

      {feedback && (
        <div className="p-3.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded border border-red-500/40 bg-red-500/10 text-red-500 text-xs">
          {error}
        </div>
      )}

      {/* Top Controls Row: Upload Custom CSV + Configure Active Dataset Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CSV Upload Card */}
        <form
          onSubmit={handleUploadCsv}
          className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3"
        >
          <div className="flex items-center gap-2">
            <FileUp className="w-4 h-4 text-blue-500" />
            <h2 className="text-xs font-semibold uppercase tracking-wider">
              Upload Transaction CSV Dataset
            </h2>
          </div>
          <p className="text-xs text-slate-500">
            Required columns: <code className="font-mono">transaction_id, timestamp, sender_account, receiver_account, amount</code>. Optional: <code className="font-mono">device_hash, ip_address, velocity_score, payment_channel</code>.
          </p>

          <input
            type="file"
            accept=".csv"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            className="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-500"
          />

          <label className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={uploadIncludeSyn}
              onChange={(e) => setUploadIncludeSyn(e.target.checked)}
              className="accent-blue-500"
            />
            <span>Also include controlled synthetic typology scenarios (tagged separately)</span>
          </label>

          <div>
            <button
              type="submit"
              disabled={!uploadFile || processing}
              className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium inline-flex items-center gap-1.5"
            >
              {processing && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              <span>Ingest CSV & Rebuild Network Graph</span>
            </button>
          </div>
        </form>

        {/* Dataset Source Mode & Sampling Controller */}
        <form
          onSubmit={handleReprocess}
          className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3"
        >
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-orange-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider">
              Configure Active Analytical Pipeline
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Dataset Mode</label>
              <select
                value={sourceMode}
                onChange={(e) => {
                  setSourceMode(e.target.value);
                  setIncludeSynthetic(e.target.value !== 'kaggle_only');
                }}
                className="w-full px-2.5 py-1.5 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-300 dark:border-slate-700"
              >
                <option value="hybrid">Hybrid (Real Kaggle CSV + Synthetic Typologies)</option>
                <option value="kaggle_only">Real Kaggle Dataset Only (100% Real Records)</option>
                <option value="synthetic_only">Controlled Synthetic Scenarios Only (Fast Demo)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] text-slate-500 mb-1">
                Real Dataset Sample Size (Rows)
              </label>
              <input
                type="number"
                min={1000}
                max={50000}
                step={1000}
                value={maxRows}
                onChange={(e) => setMaxRows(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-300 dark:border-slate-700 font-mono"
              />
            </div>
          </div>

          <p className="text-[11px] text-slate-500">
            Uses chunked Pandas scanning to prioritize multi-transaction connected accounts and preserve real shared-device clusters before converting to Parquet.
          </p>

          <button
            type="submit"
            disabled={processing}
            className="px-4 py-1.5 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 text-xs font-medium inline-flex items-center gap-1.5"
          >
            {processing && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
            <span>Re-Run Pipeline & Retrain Isolation Forest</span>
          </button>
        </form>
      </div>

      {/* Bottom Telemetry Split: Data Quality Report + ML Model Card & Evaluation */}
      {!loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Data Quality & Quarantine Card */}
          <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
              <h2 className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <span>Data Provenance & Validation Report</span>
              </h2>
              <span className="font-mono text-[11px] text-slate-500">
                {qr.processing_time_seconds}s build
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Raw Rows Scanned</div>
                <div className="font-mono text-sm font-bold mt-0.5">
                  {qr.raw_rows_scanned?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Active Indexed Rows</div>
                <div className="font-mono text-sm font-bold mt-0.5 text-emerald-500">
                  {qr.active_rows_loaded?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Real Dataset Records</div>
                <div className="font-mono text-sm font-bold mt-0.5">
                  {qr.real_dataset_rows?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">
                  Controlled Scenario Records
                </div>
                <div className="font-mono text-sm font-bold mt-0.5 text-indigo-400">
                  {qr.synthetic_scenario_rows?.toLocaleString() || 0}
                </div>
              </div>
            </div>

            <div className="space-y-1 pt-1">
              <div className="text-[11px] font-semibold uppercase text-slate-500">
                Quarantine & Sanitization Checks ({qr.quarantined_rows || 0} quarantined)
              </div>
              <div className="grid grid-cols-2 gap-1.5 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <div>
                  Missing IDs: {qr.quarantine_breakdown?.missing_required_identifiers || 0}
                </div>
                <div>
                  Invalid/Negative Amounts: {qr.quarantine_breakdown?.non_positive_or_nan_amount || 0}
                </div>
                <div>
                  Malformed Timestamps: {qr.quarantine_breakdown?.malformed_timestamp || 0}
                </div>
                <div>
                  Duplicate TX IDs: {qr.quarantine_breakdown?.duplicate_transaction_ids || 0}
                </div>
              </div>
            </div>

            <div className="text-[11px] font-mono text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-800 truncate">
              Parquet Store: {qr.parquet_cache_path} · Volume: {formatUSD(qr.total_volume_usd)}
            </div>
          </div>

          {/* ML Model Health & Evaluation Metrics Card */}
          <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
              <h2 className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-blue-500" />
                <span>Isolation Forest & Hybrid Risk Engine</span>
              </h2>
              <span className="font-mono text-[11px] text-blue-400">
                {iforest.model_version}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Train Split</div>
                <div className="font-mono font-bold text-sm mt-0.5">
                  {iforest.train_rows?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Anomalies Flagged</div>
                <div className="font-mono font-bold text-sm mt-0.5 text-red-400">
                  {iforest.anomalous_transactions_flagged || 0} ({iforest.anomaly_rate_pct}%)
                </div>
              </div>
              <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Features</div>
                <div className="font-mono font-bold text-sm mt-0.5">
                  {iforest.feature_count || 0} behavioral
                </div>
              </div>
            </div>

            <div>
              <div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">
                Unsupervised Behavioral Feature Vector
              </div>
              <div className="flex flex-wrap gap-1">
                {(iforest.features || []).map((f: string) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[10px]"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>

            {evalData.evaluation_available && (
              <div className="p-3 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="text-[11px] font-semibold uppercase text-slate-500">
                  Chronological Holdout Diagnostic vs. Dataset Labels ({evalData.test_records}{' '}
                  test TXs)
                </div>
                <div className="grid grid-cols-4 gap-2 font-mono">
                  <div>
                    <div className="text-[10px] text-slate-500">Precision</div>
                    <div className="font-bold">{evalData.precision}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">Recall</div>
                    <div className="font-bold">{evalData.recall}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">F1-Score</div>
                    <div className="font-bold">{evalData.f1_score}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">PR-AUC</div>
                    <div className="font-bold">{evalData.pr_auc}</div>
                  </div>
                </div>
                <p className="text-[10px] text-slate-500 leading-snug">{evalData.caveat}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

