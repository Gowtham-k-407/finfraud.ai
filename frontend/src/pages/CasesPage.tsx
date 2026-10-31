import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Clock, FileSearch, GitBranch, Plus } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import type { CaseRecord } from '../types/api';
import { formatShortEntity, formatTimestamp, SeverityBadge } from '../components/Badge';

const CASE_STATUSES = ['OPEN', 'IN_REVIEW', 'ESCALATED', 'CLOSED_BENIGN'];

export const CasesPage: React.FC = () => {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [noteInput, setNoteInput] = useState('');

  // Quick manual case creation modal/bar
  const [newEntity, setNewEntity] = useState('');
  const [newTitle, setNewTitle] = useState('');

  const loadCases = async (preserveId?: string) => {
    setLoading(true);
    try {
      const res = await api.listCases();
      const list = res.items || [];
      setCases(list);
      const targetId = preserveId || list[0]?.case_id;
      if (targetId) {
        const full = await api.getCase(targetId);
        setSelectedCase(full);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleSelectCase = async (caseId: string) => {
    const full = await api.getCase(caseId);
    setSelectedCase(full);
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!selectedCase) return;
    const updated = await api.updateCase(selectedCase.case_id, { status: newStatus });
    setSelectedCase(updated);
    loadCases(updated.case_id);
  };

  const handleAppendCaseNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase || !noteInput.trim()) return;
    const updated = await api.updateCase(selectedCase.case_id, { note: noteInput.trim() });
    setSelectedCase(updated);
    setNoteInput('');
  };

  const handleCreateQuickCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntity.trim() || !newTitle.trim()) return;
    const created = await api.createCase({
      title: newTitle.trim(),
      primary_entity: newEntity.trim(),
      priority: 'HIGH',
      summary: `Manual FIU investigation case opened for ${newEntity.trim()}.`,
    });
    setNewEntity('');
    setNewTitle('');
    loadCases(created.case_id);
  };

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-500" />
            <span>FIU Cases & Immutable Audit Trail</span>
          </h1>
          <p className="text-xs text-slate-500">
            Human-in-the-loop case tracking, status transitions, and evidentiary audit history
          </p>
        </div>

        <form onSubmit={handleCreateQuickCase} className="flex flex-wrap items-center gap-2 text-xs">
          <input
            type="text"
            value={newEntity}
            onChange={(e) => setNewEntity(e.target.value)}
            placeholder="Entity ID (e.g. ACC_RING_301)"
            className="w-44 px-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700 font-mono"
          />
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Case Title..."
            className="w-52 px-2.5 py-1.5 rounded bg-white dark:bg-[#0F1623] border border-slate-300 dark:border-slate-700"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium inline-flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Open Case</span>
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Case Queue */}
        <div className="rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] divide-y divide-slate-200 dark:divide-slate-800/70">
          {loading ? (
            <div className="p-6 text-xs text-slate-500">Loading cases...</div>
          ) : cases.length === 0 ? (
            <div className="p-6 text-xs text-slate-500">No investigation cases opened yet.</div>
          ) : (
            cases.map((c) => (
              <div
                key={c.case_id}
                onClick={() => handleSelectCase(c.case_id)}
                className={clsx(
                  'p-3.5 cursor-pointer transition-colors space-y-1.5',
                  selectedCase?.case_id === c.case_id
                    ? 'bg-blue-600/10 border-l-2 border-l-blue-500'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold">{c.case_id}</span>
                  <div className="flex items-center gap-1.5">
                    <SeverityBadge severity={c.priority} />
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800">
                      {c.status}
                    </span>
                  </div>
                </div>
                <div className="text-xs font-semibold truncate">{c.title}</div>
                <div className="text-[11px] text-slate-500 flex justify-between">
                  <span>{formatShortEntity(c.primary_entity)}</span>
                  <span>{c.assigned_analyst}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right Case Detail & Timeline */}
        <div className="lg:col-span-2">
          {selectedCase ? (
            <div className="p-5 rounded border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">
                      {selectedCase.case_id}
                    </span>
                    <SeverityBadge severity={selectedCase.priority} />
                  </div>
                  <h2 className="text-base font-semibold mt-1">{selectedCase.title}</h2>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">
                    Primary Entity: {selectedCase.primary_entity} · Analyst:{' '}
                    {selectedCase.assigned_analyst}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      navigate(
                        `/network?focus=${encodeURIComponent(selectedCase.primary_entity)}`
                      )
                    }
                    className="px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 text-xs inline-flex items-center gap-1"
                  >
                    <GitBranch className="w-3.5 h-3.5" />
                    <span>Graph</span>
                  </button>
                  <button
                    onClick={() =>
                      navigate(
                        `/investigations?target=${encodeURIComponent(
                          selectedCase.primary_entity
                        )}&type=ACCOUNT`
                      )
                    }
                    className="px-2.5 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs inline-flex items-center gap-1"
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    <span>Workbench</span>
                  </button>
                </div>
              </div>

              {/* Status Workflow Buttons */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-slate-500 mr-1">Disposition Workflow:</span>
                {CASE_STATUSES.map((st) => (
                  <button
                    key={st}
                    onClick={() => handleStatusChange(st)}
                    className={clsx(
                      'px-2.5 py-1 rounded text-xs font-mono border transition-colors',
                      selectedCase.status === st
                        ? 'bg-blue-600 text-white border-blue-500'
                        : 'border-slate-300 dark:border-slate-700 hover:border-blue-500'
                    )}
                  >
                    {st}
                  </button>
                ))}
              </div>

              <div className="p-3 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs leading-relaxed">
                {selectedCase.summary}
              </div>

              {/* Append Audit Log Note */}
              <form onSubmit={handleAppendCaseNote} className="flex gap-2">
                <input
                  type="text"
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Add audit log entry (e.g. Requested wire invoices from branch compliance)..."
                  className="flex-1 px-3 py-1.5 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-300 dark:border-slate-700 text-xs"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
                >
                  Log Entry
                </button>
              </form>

              {/* Chronological Audit Timeline */}
              <div className="space-y-2 pt-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Audit Trail ({selectedCase.timeline?.length || 0})</span>
                </h3>
                <div className="space-y-2">
                  {(selectedCase.timeline || []).map((ev) => (
                    <div
                      key={ev.event_id}
                      className="p-2.5 rounded border border-slate-200 dark:border-slate-800 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-1"
                    >
                      <div>
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 mr-2">
                          {ev.action}
                        </span>
                        <span className="text-slate-700 dark:text-slate-200">{ev.detail}</span>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 shrink-0">
                        {ev.actor} · {formatTimestamp(ev.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-xs text-slate-500 rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623]">
              Select a case from the queue to inspect its timeline and manage disposition.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

