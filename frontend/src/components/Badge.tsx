import React from 'react';
import clsx from 'clsx';

export function formatUSD(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || Number.isNaN(amount)) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatShortEntity(id: string): string {
  if (!id) return '';
  return id.includes(':') ? id.split(':', 2)[1] : id;
}

export function formatTimestamp(ts?: string | null): string {
  if (!ts) return '—';
  return ts.replace('T', ' ').slice(0, 19);
}

export const SeverityBadge: React.FC<{ severity?: string }> = ({ severity = 'LOW' }) => {
  const s = severity.toUpperCase();
  const styles: Record<string, string> = {
    CRITICAL:
      'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
    HIGH:
      'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30',
    MEDIUM:
      'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30',
    LOW:
      'bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30',
  };
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 text-[11px] font-mono font-semibold uppercase tracking-wider rounded border',
        styles[s] || styles.LOW
      )}
    >
      {s}
    </span>
  );
};

export const ProvenanceBadge: React.FC<{ isSynthetic?: boolean; source?: string }> = ({
  isSynthetic,
  source,
}) => {
  if (isSynthetic || source?.includes('synthetic')) {
    return (
      <span
        title="Controlled synthetic financial-crime typology scenario for deterministic verification"
        className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-tight rounded border bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border-indigo-500/25"
      >
        SYNTHETIC SCENARIO
      </span>
    );
  }
  return (
    <span
      title="Ingested from real CSV transaction dataset"
      className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-tight rounded border bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25"
    >
      REAL DATASET
    </span>
  );
};

export const PatternBadge: React.FC<{ type: string }> = ({ type }) => {
  const labels: Record<string, string> = {
    RAPID_PASS_THROUGH: 'LAYERING / PASS-THROUGH',
    CIRCULAR_FLOW: 'CIRCULAR RING',
    FAN_IN: 'FAN-IN HUB',
    FAN_OUT: 'FAN-OUT HUB',
    SHARED_DEVICE: 'SHARED DEVICE',
    SHARED_IP: 'SHARED IP / PROXY',
    MULE_ACCOUNT_INDICATOR: 'POTENTIAL MULE INDICATOR',
  };
  return (
    <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-medium rounded bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
      {labels[type] || type}
    </span>
  );
};

