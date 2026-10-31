import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  FileSearch,
  GitBranch,
  HelpCircle,
  MessageSquarePlus,
  Scale,
  ShieldAlert,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import type { InvestigationReport, PatternDetection } from '../types/api';
import {
  formatShortEntity,
  formatTimestamp,
  formatUSD,
  PatternBadge,
  ProvenanceBadge,
  SeverityBadge,
} from '../components/Badge';

export const InvestigationWorkspacePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [detections, setDetections] = useState<PatternDetection[]>([]);
  const [patternFilter, setPatternFilter] = useState('');
  const [customTarget, setCustomTarget] = useState(searchParams.get('target') || '');
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Analyst Note & Case Escalation state
  const [noteText, setNoteText] = useState('');
  const [caseCreatedMsg, setCaseCreatedMsg] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDetections()
      .then((res) => {
        setDetections(res.items || []);
        const paramTarget = searchParams.get('target');
        const paramType = searchParams.get('type') || 'ACCOUNT';
        if (paramTarget) {
          triggerInvestigation(paramTarget, paramType);
        } else if (res.items && res.items.length > 0) {
          triggerInvestigation(res.items[0].primary_entity, 'ACCOUNT');
        }
      })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const triggerInvestigation = async (targetId: string, targetType = 'ACCOUNT') => {
    setLoadingReport(true);
    setError(null);
    setCaseCreatedMsg(null);
    setCustomTarget(targetId);
    setSearchParams({ target: targetId, type: targetType });
    try {
      const rep = await api.runInvestigation(targetId, targetType, true);
      setReport(rep);
    } catch (err: any) {
      setError(err.message || 'Investigation synthesis failed');
    } finally {
      setLoadingReport(false);
    }
  };

  const handleVerdict = async (hypothesisId: string, verdict: 'USEFUL' | 'REJECTED') => {
    if (!report) return;
    try {
      const updated = await api.addInvestigationNote(report.investigation_id, {
        author: 'FIU Senior Investigator',
        content: `Marked hypothesis ${hypothesisId} as ${verdict}.`,
        hypothesis_id: hypothesisId,
        verdict,
      });
      setReport(updated);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!report || !noteText.trim()) return;
    try {
      const updated = await api.addInvestigationNote(report.investigation_id, {
        author: 'FIU Senior Investigator',
        content: noteText.trim(),
      });
      setReport(updated);
      setNoteText('');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleEscalateCase = async () => {
    if (!report) return;
    try {
      const created = await api.createCase({
        title: `Investigation Escalation — ${formatShortEntity(report.target_id)}`,
        primary_entity: report.target_id,
        priority: report.overall_priority,
        assigned_analyst: 'A. Sharma (FIU Lead)',
        investigation_id: report.investigation_id,
        summary: report.executive_summary,
      });
      setCaseCreatedMsg(`Escalated to FIU Case ${created.case_id}`);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const filteredDetections = patternFilter
    ? detections.filter((d) => d.pattern_type === patternFilter)
    : detections;

  const directFacts = (report?.verified_facts || []).filter((f) => f.is_direct_fact);
  const analyticalSignals = (report?.verified_facts || []).filter((f) => !f.is_direct_fact);

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex flex-col lg:flex-row">
      {/* Left Rail: Detected Suspicious Patterns Queue */}
      <aside className="w-full lg:w-96 border-b lg:border-b-0 lg:border-r border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] flex flex-col max-h-[380px] lg:max-h-[calc(100vh-3.5rem)]">
        <div className="p-3.5 border-b border-slate-200 dark:border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-red-500" />
              <span>Detected Patterns ({filteredDetections.length})</span>
            </h2>
            <select
              value={patternFilter}
              onChange={(e) => setPatternFilter(e.target.value)}
              aria-label="Filter detections by typology"
              className="px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 text-[11px]"
            >
              <option value="">All Typologies</option>
              <option value="RAPID_PASS_THROUGH">Layering / Pass-Through</option>
              <option value="CIRCULAR_FLOW">Circular Rings</option>
              <option value="FAN_IN">Fan-In</option>
              <option value="FAN_OUT">Fan-Out</option>
              <option value="SHARED_DEVICE">Shared Device</option>
              <option value="SHARED_IP">Shared IP</option>
              <option value="MULE_ACCOUNT_INDICATOR">Mule Indicators</option>
            </select>
          </div>

          {/* Direct Entity Investigation Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (customTarget.trim()) triggerInvestigation(customTarget.trim(), 'ACCOUNT');
            }}
            className="flex gap-1.5"
          >
            <input
              type="text"
              value={customTarget}
              onChange={(e) => setCustomTarget(e.target.value)}
              placeholder="Account or Detection ID..."
              className="flex-1 px-2.5 py-1.5 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 font-mono text-xs"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
            >
              Run
            </button>
          </form>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-200 dark:divide-slate-800/70">
          {filteredDetections.map((det) => {
            const active =
              report?.target_id === det.primary_entity ||
              report?.target_id === det.detection_id;
            return (
              <div
                key={det.detection_id}
                onClick={() => triggerInvestigation(det.primary_entity, 'ACCOUNT')}
                className={clsx(
                  'p-3 cursor-pointer transition-colors space-y-1.5',
                  active
                    ? 'bg-blue-600/10 border-l-2 border-l-blue-500'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <PatternBadge type={det.pattern_type} />
                  <div className="flex items-center gap-1.5">
                    <SeverityBadge severity={det.severity} />
                    <span className="font-mono text-xs font-bold">{det.risk_score}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-900 dark:text-white truncate">
                    {formatShortEntity(det.primary_entity)}
                  </span>
                  <ProvenanceBadge
                    isSynthetic={det.is_synthetic_scenario}
                    source={det.data_source}
                  />
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-2">
                  {det.summary}
                </p>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Right Main Workbench: Structured Evidence, Competing Hypotheses & Narrative */}
      <div className="flex-1 p-4 lg:p-6 overflow-y-auto space-y-5 max-w-6xl">
        {error && (
          <div className="p-3.5 rounded border border-red-500/40 bg-red-500/10 text-red-500 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loadingReport ? (
          <div className="space-y-4">
            <div className="h-28 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="h-64 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse" />
              <div className="h-64 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] animate-pulse" />
            </div>
          </div>
        ) : report ? (
          <>
            {/* Investigation Header */}
            <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs text-slate-500">
                      {report.investigation_id}
                    </span>
                    <SeverityBadge severity={report.overall_priority} />
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/25">
                      <Sparkles className="w-3 h-3" />
                      {report.generation_mode === 'llm_grounded'
                        ? `LLM GROUNDED (${report.llm_provider})`
                        : 'DETERMINISTIC EVIDENCE ENGINE'}
                    </span>
                  </div>
                  <h1 className="mt-1.5 text-lg font-mono font-bold text-slate-900 dark:text-white">
                    Target: {formatShortEntity(report.target_id)}{' '}
                    <span className="text-sm font-normal text-slate-500">
                      (Composite Score: {report.composite_risk_score}/100 · Analyzed Flow:{' '}
                      {formatUSD(report.total_volume_analyzed)})
                    </span>
                  </h1>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() =>
                      navigate(`/network?focus=${encodeURIComponent(report.target_id)}`)
                    }
                    className="px-3 py-1.5 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 text-xs font-medium inline-flex items-center gap-1.5"
                  >
                    <GitBranch className="w-3.5 h-3.5 text-blue-400" />
                    <span>View in Network Graph</span>
                  </button>
                  <button
                    onClick={handleEscalateCase}
                    className="px-3 py-1.5 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-medium inline-flex items-center gap-1.5"
                  >
                    <Briefcase className="w-3.5 h-3.5" />
                    <span>Escalate to FIU Case</span>
                  </button>
                </div>
              </div>

              {caseCreatedMsg && (
                <div className="px-3 py-2 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-300 text-xs flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5 font-medium">
                    <CheckCircle2 className="w-4 h-4" />
                    {caseCreatedMsg}
                  </span>
                  <button
                    onClick={() => navigate('/cases')}
                    className="underline font-mono text-[11px]"
                  >
                    Open Cases Queue →
                  </button>
                </div>
              )}

              {/* Provenance Banner */}
              <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/60 px-3 py-1.5 rounded border border-slate-200 dark:border-slate-800">
                {report.data_provenance_note}
              </div>

              {/* Executive Narrative */}
              <div className="p-3.5 rounded bg-blue-500/5 border border-blue-500/20">
                <div className="text-[10px] font-mono uppercase tracking-wider text-blue-500 font-semibold mb-1">
                  Evidence-Grounded Investigation Narrative (Interpretive Synthesis)
                </div>
                <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-200">
                  {report.executive_summary}
                </p>
              </div>

              {/* Suspicious Multi-Hop Paths if present */}
              {report.suspicious_paths.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-mono uppercase text-slate-500">
                    Reconstructed Multi-Hop Flow Path(s)
                  </div>
                  {report.suspicious_paths.map((p, idx) => (
                    <div
                      key={idx}
                      className="px-3 py-1.5 rounded bg-red-500/10 border border-red-500/25 font-mono text-xs text-red-600 dark:text-red-300 overflow-x-auto whitespace-nowrap"
                    >
                      {p.map(formatShortEntity).join('  ⟶  ')}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Epistemic Split: Verified Direct Facts vs. Analytical Pattern/ML Signals */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Left: Verified Direct Ledger & Session Facts */}
              <div className="p-4 rounded border border-emerald-500/30 bg-white dark:bg-[#0F1623] space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                  <div>
                    <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                      1. Verified Direct Facts ({directFacts.length})
                    </h2>
                    <p className="text-[11px] text-slate-500">
                      Immutable transaction ledger records & raw session telemetry
                    </p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-500">
                    OBSERVED FACT
                  </span>
                </div>

                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {directFacts.map((ev) => (
                    <div
                      key={ev.evidence_id}
                      className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-mono">
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">
                          [{ev.evidence_id}] {ev.title}
                        </span>
                        <span className="text-[10px] text-slate-500">{ev.category}</span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
                        {ev.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: Analytical Inferences & Pattern Signals */}
              <div className="p-4 rounded border border-amber-500/30 bg-white dark:bg-[#0F1623] space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                  <div>
                    <h2 className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                      2. Analytical Pattern & ML Signals ({analyticalSignals.length})
                    </h2>
                    <p className="text-[11px] text-slate-500">
                      Algorithmic graph detections & Isolation Forest anomaly indicators
                    </p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-400">
                    MODEL INFERENCE
                  </span>
                </div>

                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {analyticalSignals.length === 0 ? (
                    <div className="text-xs text-slate-500 py-6 text-center">
                      No elevated graph typology or Isolation Forest anomalies triggered for this entity.
                    </div>
                  ) : (
                    analyticalSignals.map((ev) => (
                      <div
                        key={ev.evidence_id}
                        className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between font-mono">
                          <span className="font-bold text-amber-600 dark:text-amber-400">
                            [{ev.evidence_id}] {ev.title}
                          </span>
                          <span className="text-[10px] text-slate-500">
                            Confidence: {ev.confidence}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
                          {ev.description}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Competing Hypotheses Evaluation Matrix */}
            <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3">
              <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
                <Scale className="w-4 h-4 text-blue-500" />
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wider">
                    3. Competing Investigation Hypotheses (Suspicious vs. Benign Explanations)
                  </h2>
                  <p className="text-[11px] text-slate-500">
                    Analysts must evaluate contradicting and missing evidence before disposition
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {report.hypotheses.map((hyp) => {
                  const isBenign = hyp.category === 'BENIGN_ALTERNATIVE';
                  return (
                    <div
                      key={hyp.hypothesis_id}
                      className={clsx(
                        'p-3.5 rounded border flex flex-col justify-between space-y-3',
                        isBenign
                          ? 'border-blue-500/30 bg-blue-500/[0.03]'
                          : 'border-red-500/30 bg-red-500/[0.03]'
                      )}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={clsx(
                              'text-[10px] font-mono font-semibold px-2 py-0.5 rounded',
                              isBenign
                                ? 'bg-blue-500/15 text-blue-500'
                                : 'bg-red-500/15 text-red-400'
                            )}
                          >
                            {hyp.hypothesis_id} ·{' '}
                            {isBenign ? 'BENIGN ALTERNATIVE' : 'SUSPICIOUS TYPOLOGY'}
                          </span>
                          <span className="text-[11px] font-mono text-slate-500">
                            Confidence: <strong>{hyp.confidence}</strong>
                          </span>
                        </div>

                        <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                          {hyp.title}
                        </h3>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                          {hyp.description}
                        </p>

                        <div className="space-y-1 text-[11px]">
                          <div>
                            <span className="font-semibold text-emerald-500">Supporting: </span>
                            <span className="font-mono text-slate-600 dark:text-slate-300">
                              {hyp.supporting_evidence.join(', ') || 'None'}
                            </span>
                          </div>
                          <div>
                            <span className="font-semibold text-amber-500">Contradicting: </span>
                            <span className="text-slate-600 dark:text-slate-300">
                              {hyp.contradicting_evidence.join('; ')}
                            </span>
                          </div>
                          <div>
                            <span className="font-semibold text-slate-500">Missing KYC/Docs: </span>
                            <span className="text-slate-500 dark:text-slate-400">
                              {hyp.missing_evidence.join(' ')}
                            </span>
                          </div>
                        </div>

                        <div className="p-2 rounded bg-slate-100 dark:bg-slate-900/80 text-[11px]">
                          <span className="font-semibold">Next Step: </span>
                          {hyp.recommended_next_step}
                        </div>
                      </div>

                      {/* Human-in-the-loop Hypothesis Verdict Controls */}
                      <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                        <span className="text-[10px] font-mono text-slate-500">
                          Analyst Verdict:{' '}
                          <strong className="text-slate-700 dark:text-slate-200">
                            {hyp.analyst_verdict || 'PENDING REVIEW'}
                          </strong>
                        </span>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleVerdict(hyp.hypothesis_id, 'USEFUL')}
                            className={clsx(
                              'px-2 py-1 rounded text-[11px] inline-flex items-center gap-1 border',
                              hyp.analyst_verdict === 'USEFUL'
                                ? 'bg-emerald-600 text-white border-emerald-500'
                                : 'border-slate-300 dark:border-slate-700 hover:border-emerald-500'
                            )}
                          >
                            <ThumbsUp className="w-3 h-3" />
                            <span>Corroborate</span>
                          </button>
                          <button
                            onClick={() => handleVerdict(hyp.hypothesis_id, 'REJECTED')}
                            className={clsx(
                              'px-2 py-1 rounded text-[11px] inline-flex items-center gap-1 border',
                              hyp.analyst_verdict === 'REJECTED'
                                ? 'bg-red-600 text-white border-red-500'
                                : 'border-slate-300 dark:border-slate-700 hover:border-red-500'
                            )}
                          >
                            <ThumbsDown className="w-3 h-3" />
                            <span>Reject</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Bottom Row: Recommended Human Review Actions, Limitations & Analyst Notes */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3">
                <h2 className="text-xs font-semibold uppercase tracking-wider">
                  Recommended Human Investigation Actions
                </h2>
                <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
                  {report.recommended_actions.map((act, i) => (
                    <li
                      key={i}
                      className="p-2 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800"
                    >
                      {act}
                    </li>
                  ))}
                </ul>

                <div className="pt-2 border-t border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] font-semibold uppercase text-slate-500 flex items-center gap-1 mb-1.5">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>Evidence & Model Limitations</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                    {report.evidence_limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Human Investigator Notes Log */}
              <div className="p-4 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-3 flex flex-col justify-between">
                <div className="space-y-2">
                  <h2 className="text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5">
                    <MessageSquarePlus className="w-4 h-4 text-blue-400" />
                    <span>Investigator Audit Notes ({report.notes.length})</span>
                  </h2>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {report.notes.length === 0 ? (
                      <p className="text-xs text-slate-500 py-4">
                        No human analyst annotations recorded yet for this report.
                      </p>
                    ) : (
                      report.notes.map((n) => (
                        <div
                          key={n.note_id}
                          className="p-2.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs"
                        >
                          <div className="flex justify-between text-[10px] font-mono text-slate-500">
                            <span>{n.author}</span>
                            <span>{formatTimestamp(n.created_at)}</span>
                          </div>
                          <p className="mt-1 text-slate-700 dark:text-slate-200">{n.content}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <form onSubmit={handleAddNote} className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <textarea
                    rows={2}
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Record investigative observation, KYC finding, or false-positive rationale..."
                    className="w-full p-2 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 text-xs focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
                  >
                    Append Audit Note
                  </button>
                </form>
              </div>
            </div>
          </>
        ) : (
          <div className="py-16 text-center text-slate-500 text-xs">
            Select a detected suspicious pattern on the left or enter an entity ID to begin investigation.
          </div>
        )}
      </div>
    </div>
  );
};

