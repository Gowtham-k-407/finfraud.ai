import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import ForceGraph2D, { ForceGraphMethods } from 'react-force-graph-2d';
import {
  Cpu,
  Eye,
  EyeOff,
  FileSearch,
  Filter,
  GitBranch,
  Globe,
  Maximize2,
  RefreshCw,
  Route,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import type { EntityDetail, GraphLink, GraphNode, GraphPayload } from '../types/api';
import {
  formatShortEntity,
  formatTimestamp,
  formatUSD,
  PatternBadge,
  ProvenanceBadge,
  SeverityBadge,
} from '../components/Badge';

const QUICK_SCENARIOS = [
  { label: 'All Priority Networks', focus: '', pattern: '', source: 'all' },
  { label: 'Mule Layering Chain', focus: 'ACCOUNT:ACC_MULE_7701', pattern: '', source: 'all' },
  { label: 'Circular Wash Ring', focus: 'ACCOUNT:ACC_RING_301', pattern: '', source: 'all' },
  { label: 'Fan-In / Fan-Out Hub', focus: 'ACCOUNT:ACC_HUB_4400', pattern: '', source: 'all' },
  { label: 'Shared Device Farm', focus: 'DEVICE:DEV_EMU_X88', pattern: '', source: 'all' },
  { label: 'Benign Office NAT (Control)', focus: 'IP:203.0.113.10', pattern: '', source: 'all' },
  { label: 'Real Kaggle Records Only', focus: '', pattern: '', source: 'real_only' },
];

export const NetworkExplorerPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const fgRef = useRef<ForceGraphMethods<any, any> | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [dimensions, setDimensions] = useState({ width: 900, height: 640 });
  const [graphData, setGraphData] = useState<GraphPayload>({
    nodes: [],
    links: [],
    meta: { node_count: 0, link_count: 0 },
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & controls
  const [searchQuery, setSearchQuery] = useState(searchParams.get('focus') || '');
  const [patternFilter, setPatternFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [minRisk, setMinRisk] = useState(0);
  const [includeDevices, setIncludeDevices] = useState(true);
  const [includeIps, setIncludeIps] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  // Path finder
  const [pathSource, setPathSource] = useState('');
  const [pathTarget, setPathTarget] = useState('');
  const [highlightedPathNodes, setHighlightedPathNodes] = useState<Set<string>>(new Set());
  const [pathMessage, setPathMessage] = useState<string | null>(null);

  // Selected entity inspector
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(
    searchParams.get('focus') || null
  );
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Responsive canvas sizing
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(320, Math.floor(rect.width)),
          height: Math.max(460, Math.floor(rect.height)),
        });
      }
    };
    updateSize();
    const obs = new ResizeObserver(updateSize);
    if (containerRef.current) obs.observe(containerRef.current);
    window.addEventListener('resize', updateSize);
    return () => {
      obs.disconnect();
      window.removeEventListener('resize', updateSize);
    };
  }, [selectedEntityId]);

  const loadSubgraph = useCallback(
    async (overrideFocus?: string, overrideSource?: string, overridePattern?: string) => {
      setLoading(true);
      setError(null);
      setHighlightedPathNodes(new Set());
      setPathMessage(null);
      try {
        const focusTarget = overrideFocus !== undefined ? overrideFocus : searchQuery.trim();
        let res: GraphPayload;
        if (focusTarget) {
          try {
            res = await api.getEgoGraph(focusTarget, 2, 130);
          } catch {
            res = await api.getSubgraph({
              search: focusTarget,
              include_devices: includeDevices,
              include_ips: includeIps,
              max_nodes: 130,
            });
          }
        } else {
          res = await api.getSubgraph({
            pattern_type: overridePattern !== undefined ? overridePattern : patternFilter,
            min_risk: minRisk,
            include_devices: includeDevices,
            include_ips: includeIps,
            data_source_filter: overrideSource !== undefined ? overrideSource : sourceFilter,
            max_nodes: 135,
          });
        }
        setGraphData(res);
        setTimeout(() => {
          fgRef.current?.zoomToFit(450, 48);
        }, 250);
      } catch (err: any) {
        setError(err.message || 'Failed to load network graph');
      } finally {
        setLoading(false);
      }
    },
    [searchQuery, patternFilter, minRisk, includeDevices, includeIps, sourceFilter]
  );

  useEffect(() => {
    const focusParam = searchParams.get('focus');
    if (focusParam) {
      setSearchQuery(focusParam);
      setSelectedEntityId(focusParam);
      loadSubgraph(focusParam);
    } else {
      loadSubgraph('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.get('focus')]);

  // Load entity detail whenever selectedEntityId changes
  useEffect(() => {
    if (!selectedEntityId) {
      setEntityDetail(null);
      return;
    }
    setDetailLoading(true);
    api
      .getEntityDetail(selectedEntityId)
      .then((det) => setEntityDetail(det))
      .catch(() => setEntityDetail(null))
      .finally(() => setDetailLoading(false));
  }, [selectedEntityId]);

  const handleExpandEgo = async (entityId: string, hops: number) => {
    setLoading(true);
    try {
      const res = await api.getEgoGraph(entityId, hops, 150);
      setGraphData(res);
      setSelectedEntityId(entityId);
      setTimeout(() => fgRef.current?.zoomToFit(400, 50), 220);
    } catch (err: any) {
      setError(err.message || 'Unable to expand ego network');
    } finally {
      setLoading(false);
    }
  };

  const handleFindPath = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pathSource.trim() || !pathTarget.trim()) return;
    setPathMessage(null);
    try {
      const res = await api.findPaths(pathSource.trim(), pathTarget.trim(), 6);
      const allPaths = [...res.directed_paths, ...res.infrastructure_paths];
      if (allPaths.length === 0) {
        setPathMessage('No directed or shared-infrastructure path found within 6 hops.');
        setHighlightedPathNodes(new Set());
        return;
      }
      const pathSet = new Set<string>();
      allPaths.forEach((p) => p.forEach((n) => pathSet.add(n)));
      setHighlightedPathNodes(pathSet);
      setPathMessage(
        `Highlighted ${res.directed_paths.length} directed flow path(s) & ${res.infrastructure_paths.length} topology path(s): ` +
          allPaths[0].map(formatShortEntity).join(' → ')
      );
      // Ensure path nodes are visible by loading ego around source if needed
      const presentIds = new Set(graphData.nodes.map((n) => n.id));
      if (!presentIds.has(res.source) || !presentIds.has(res.target)) {
        const ego = await api.getEgoGraph(res.source, 3, 150);
        setGraphData(ego);
      }
    } catch (err: any) {
      setPathMessage(err.message || 'Path lookup failed');
    }
  };

  // Neighbor lookup for hover/selection highlighting
  const neighborMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    graphData.links.forEach((l) => {
      const s = typeof l.source === 'object' ? l.source.id : l.source;
      const t = typeof l.target === 'object' ? l.target.id : l.target;
      if (!map.has(s)) map.set(s, new Set());
      if (!map.has(t)) map.set(t, new Set());
      map.get(s)!.add(t);
      map.get(t)!.add(s);
    });
    return map;
  }, [graphData.links]);

  const activeFocusResolved = entityDetail?.entity_id || selectedEntityId;

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x || 0;
      const y = node.y || 0;
      const isSelected = activeFocusResolved === node.id;
      const isNeighbor =
        activeFocusResolved && neighborMap.get(activeFocusResolved)?.has(node.id);
      const isInPath = highlightedPathNodes.has(node.id);

      const dimmed =
        (highlightedPathNodes.size > 0 && !isInPath) ||
        (activeFocusResolved &&
          highlightedPathNodes.size === 0 &&
          !isSelected &&
          !isNeighbor);

      const baseRadius =
        node.entity_type === 'ACCOUNT'
          ? Math.min(9.5, 4.8 + Math.log1p(node.total_tx_count || 1) * 1.4)
          : 5.5;

      ctx.save();
      ctx.globalAlpha = dimmed ? 0.22 : 1.0;

      // Selection or Path Halo
      if (isSelected || isInPath) {
        ctx.beginPath();
        ctx.arc(x, y, baseRadius + 4.5, 0, 2 * Math.PI, false);
        ctx.fillStyle = isInPath ? 'rgba(250, 204, 21, 0.32)' : 'rgba(239, 68, 68, 0.28)';
        ctx.fill();
        ctx.lineWidth = 1.6 / globalScale;
        ctx.strokeStyle = isInPath ? '#FACC15' : '#FFFFFF';
        ctx.stroke();
      }

      ctx.fillStyle = node.color || '#3B82F6';
      ctx.beginPath();
      if (node.entity_type === 'DEVICE') {
        // Square glyph for Device fingerprint
        const s = baseRadius * 1.65;
        ctx.rect(x - s / 2, y - s / 2, s, s);
      } else if (node.entity_type === 'IP_ADDRESS') {
        // Diamond glyph for IP address
        const r = baseRadius * 1.3;
        ctx.moveTo(x, y - r);
        ctx.lineTo(x + r, y);
        ctx.lineTo(x, y + r);
        ctx.lineTo(x - r, y);
        ctx.closePath();
      } else {
        // Circle for Account
        ctx.arc(x, y, baseRadius, 0, 2 * Math.PI, false);
      }
      ctx.fill();

      ctx.lineWidth = 1.1 / globalScale;
      ctx.strokeStyle = isSelected ? '#FFFFFF' : 'rgba(15, 23, 42, 0.85)';
      ctx.stroke();

      // Clean readable label
      if (
        showLabels &&
        (globalScale >= 1.15 || isSelected || isInPath || node.risk_score >= 65)
      ) {
        const label = node.label || formatShortEntity(node.id);
        const fontSize = Math.max(3.2, 10.5 / globalScale);
        ctx.font = `600 ${fontSize}px "JetBrains Mono", monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = dimmed ? 'rgba(148, 163, 184, 0.45)' : '#E2E8F0';
        ctx.fillText(label, x, y + baseRadius + 2 / globalScale);
      }
      ctx.restore();
    },
    [activeFocusResolved, neighborMap, highlightedPathNodes, showLabels]
  );

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Top Explorer Filter & Scenario Ribbon */}
      <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0F1623] space-y-2">
        {/* Preset Scenarios Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
          <span className="text-[10px] font-mono uppercase text-slate-500 mr-1 shrink-0">
            Quick Focus:
          </span>
          {QUICK_SCENARIOS.map((sc) => (
            <button
              key={sc.label}
              onClick={() => {
                setSearchQuery(sc.focus);
                setSourceFilter(sc.source);
                setPatternFilter(sc.pattern);
                setSelectedEntityId(sc.focus || null);
                if (sc.focus) {
                  setSearchParams({ focus: sc.focus });
                } else {
                  setSearchParams({});
                }
                loadSubgraph(sc.focus, sc.source, sc.pattern);
              }}
              className={clsx(
                'px-2.5 py-1 rounded text-[11px] font-medium whitespace-nowrap border transition-colors',
                (sc.focus && selectedEntityId === sc.focus) ||
                  (!sc.focus && !selectedEntityId && sourceFilter === sc.source)
                  ? 'bg-blue-600 text-white border-blue-500'
                  : 'bg-slate-100 dark:bg-[#151F32] text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700/80 hover:border-blue-500'
              )}
            >
              {sc.label}
            </button>
          ))}
        </div>

        {/* Filter & Path Discovery Controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (searchQuery.trim()) setSelectedEntityId(searchQuery.trim());
              loadSubgraph();
            }}
            className="flex items-center gap-1"
          >
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Entity ID (e.g. ACC_MULE_7701)"
                className="w-48 pl-7 pr-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 font-mono text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium"
            >
              Filter
            </button>
          </form>

          <select
            value={patternFilter}
            onChange={(e) => {
              setPatternFilter(e.target.value);
              setSearchQuery('');
              loadSubgraph('', sourceFilter, e.target.value);
            }}
            aria-label="Filter by typology pattern"
            className="px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 text-xs"
          >
            <option value="">All Pattern Typologies</option>
            <option value="RAPID_PASS_THROUGH">Layering / Pass-Through</option>
            <option value="CIRCULAR_FLOW">Circular Wash Rings</option>
            <option value="FAN_IN">Fan-In Collection Hubs</option>
            <option value="FAN_OUT">Fan-Out Dispersion Hubs</option>
            <option value="SHARED_DEVICE">Shared Device Clusters</option>
            <option value="SHARED_IP">Shared IP / Proxy Clusters</option>
            <option value="MULE_ACCOUNT_INDICATOR">Potential Mule Indicators</option>
          </select>

          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700">
            <Filter className="w-3 h-3 text-slate-400" />
            <span className="text-[11px] text-slate-500">Min Risk:</span>
            <input
              type="range"
              min={0}
              max={80}
              step={10}
              value={minRisk}
              onChange={(e) => setMinRisk(Number(e.target.value))}
              onMouseUp={() => loadSubgraph()}
              className="w-16 accent-blue-500"
            />
            <span className="font-mono text-[11px] w-5">{minRisk}</span>
          </div>

          <label className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={includeDevices}
              onChange={(e) => setIncludeDevices(e.target.checked)}
              className="accent-orange-500"
            />
            <span className="text-[11px]">Devices</span>
          </label>

          <label className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={includeIps}
              onChange={(e) => setIncludeIps(e.target.checked)}
              className="accent-purple-500"
            />
            <span className="text-[11px]">IPs</span>
          </label>

          <button
            onClick={() => setShowLabels((s) => !s)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-[#151F32]"
            title="Toggle node labels"
          >
            {showLabels ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span className="text-[11px]">Labels</span>
          </button>

          {/* Path Tracer */}
          <form onSubmit={handleFindPath} className="hidden xl:flex items-center gap-1 ml-auto">
            <Route className="w-3.5 h-3.5 text-amber-400" />
            <input
              type="text"
              value={pathSource}
              onChange={(e) => setPathSource(e.target.value)}
              placeholder="From (e.g. ACC_FEED_7101)"
              className="w-36 px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 font-mono text-[11px]"
            />
            <span className="text-slate-400">→</span>
            <input
              type="text"
              value={pathTarget}
              onChange={(e) => setPathTarget(e.target.value)}
              placeholder="To (e.g. ACC_EXIT_7704)"
              className="w-36 px-2 py-1 rounded bg-slate-100 dark:bg-[#151F32] border border-slate-200 dark:border-slate-700 font-mono text-[11px]"
            />
            <button
              type="submit"
              className="px-2 py-1 rounded bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 text-[11px] font-medium"
            >
              Trace Path
            </button>
          </form>

          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedEntityId(null);
              setHighlightedPathNodes(new Set());
              setPathMessage(null);
              setSearchParams({});
              loadSubgraph('');
            }}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-200 dark:border-slate-700 hover:border-blue-500 text-[11px]"
            title="Reset graph layout & filters"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Reset</span>
          </button>
        </div>

        {pathMessage && (
          <div className="px-3 py-1.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-xs font-mono flex items-center justify-between">
            <span className="truncate">{pathMessage}</span>
            <button
              onClick={() => {
                setHighlightedPathNodes(new Set());
                setPathMessage(null);
              }}
              className="ml-2 text-amber-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Main Split Workspace: Interactive Force Graph Canvas + Slide-in Entity Inspector */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Graph Canvas Container */}
        <div
          ref={containerRef}
          className="flex-1 relative bg-[#070B12] overflow-hidden select-none"
        >
          {loading && (
            <div className="absolute inset-0 z-20 bg-[#070B12]/75 backdrop-blur-sm flex items-center justify-center">
              <div className="px-4 py-2.5 rounded border border-slate-700 bg-[#0F1623] text-xs font-mono text-slate-200 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />
                <span>Reconstructing bounded heterogeneous relationship subgraph...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute top-4 left-4 z-20 p-3 rounded border border-red-500/40 bg-red-950/90 text-red-200 text-xs max-w-md">
              {error}
            </div>
          )}

          <ForceGraph2D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            backgroundColor="#070B12"
            nodeRelSize={5}
            nodeCanvasObject={paintNode}
            onNodeClick={(node: any) => {
              setSelectedEntityId(node.id);
              fgRef.current?.centerAt(node.x, node.y, 400);
            }}
            linkColor={(link: any) => {
              const s = typeof link.source === 'object' ? link.source.id : link.source;
              const t = typeof link.target === 'object' ? link.target.id : link.target;
              if (highlightedPathNodes.has(s) && highlightedPathNodes.has(t)) {
                return '#FACC15';
              }
              if (link.relationship_type === 'ACCOUNT_USED_DEVICE') {
                return 'rgba(249, 115, 22, 0.52)';
              }
              if (link.relationship_type === 'ACCOUNT_USED_IP') {
                return 'rgba(168, 85, 247, 0.48)';
              }
              return 'rgba(148, 163, 184, 0.42)';
            }}
            linkWidth={(link: any) => {
              const s = typeof link.source === 'object' ? link.source.id : link.source;
              const t = typeof link.target === 'object' ? link.target.id : link.target;
              if (highlightedPathNodes.has(s) && highlightedPathNodes.has(t)) return 2.6;
              return link.relationship_type === 'ACCOUNT_SENT_TO_ACCOUNT' ? 1.4 : 1.0;
            }}
            linkDirectionalArrowLength={(link: any) =>
              link.relationship_type === 'ACCOUNT_SENT_TO_ACCOUNT' ? 4.5 : 0
            }
            linkDirectionalArrowRelPos={1}
            linkDirectionalParticles={(link: any) => {
              const s = typeof link.source === 'object' ? link.source.id : link.source;
              const t = typeof link.target === 'object' ? link.target.id : link.target;
              if (highlightedPathNodes.has(s) && highlightedPathNodes.has(t)) return 3;
              return link.relationship_type === 'ACCOUNT_SENT_TO_ACCOUNT' &&
                link.total_amount >= 4000
                ? 2
                : 0;
            }}
            linkDirectionalParticleWidth={2.2}
            cooldownTicks={90}
          />

          {/* Top-Left Subgraph Telemetry Pill */}
          <div className="absolute top-3 left-3 px-3 py-1.5 rounded bg-[#0F1623]/90 border border-slate-800 text-[11px] font-mono text-slate-300 flex items-center gap-3">
            <span>Nodes: {graphData.nodes.length}</span>
            <span>Edges: {graphData.links.length}</span>
            <button
              onClick={() => fgRef.current?.zoomToFit(400, 45)}
              className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-1"
              title="Fit graph to screen"
            >
              <Maximize2 className="w-3 h-3" />
              <span>Fit</span>
            </button>
          </div>

          {/* Bottom-Left Mandatory Indicator Legend & Epistemic Disclaimer */}
          <div className="absolute bottom-3 left-3 p-3 rounded bg-[#0F1623]/92 border border-slate-800 text-[11px] text-slate-300 max-w-sm space-y-1.5">
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
              Entity & Risk Indicator Legend
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444] shrink-0" />
                <span>Suspected Mule / High-Risk</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#F97316] shrink-0" />
                <span>Shared Device Indicator</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rotate-45 bg-[#A855F7] shrink-0" />
                <span>Shared IP / Proxy Indicator</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#3B82F6] shrink-0" />
                <span>Normal Baseline Account</span>
              </div>
            </div>
            <div className="text-[10px] text-slate-400 border-t border-slate-800 pt-1 leading-snug">
              Note: Colors represent analytical indicators or technical entity roles, never verified criminal guilt.
            </div>
          </div>
        </div>

        {/* Right Entity Intelligence Details Panel */}
        {selectedEntityId && (
          <aside className="w-full sm:w-[400px] lg:w-[430px] border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F1623] overflow-y-auto flex flex-col z-20">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between gap-2 sticky top-0 bg-white dark:bg-[#0F1623] z-10">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {entityDetail?.entity_type || 'ENTITY'}
                  </span>
                  {entityDetail?.profile && (
                    <ProvenanceBadge isSynthetic={entityDetail.profile.is_synthetic} />
                  )}
                </div>
                <h2 className="mt-1 font-mono text-base font-bold text-slate-900 dark:text-white truncate">
                  {entityDetail?.label || formatShortEntity(selectedEntityId)}
                </h2>
              </div>
              <button
                onClick={() => setSelectedEntityId(null)}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
                aria-label="Close entity details"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {detailLoading || !entityDetail ? (
              <div className="p-6 space-y-3">
                <div className="h-16 rounded bg-slate-100 dark:bg-slate-800/60 animate-pulse" />
                <div className="h-28 rounded bg-slate-100 dark:bg-slate-800/60 animate-pulse" />
                <div className="h-40 rounded bg-slate-100 dark:bg-slate-800/60 animate-pulse" />
              </div>
            ) : (
              <div className="p-4 space-y-4 text-xs">
                {/* Action Bar: Multi-hop Ego Expansion & AI Investigation */}
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() =>
                      navigate(
                        `/investigations?target=${encodeURIComponent(
                          entityDetail.entity_id
                        )}&type=ACCOUNT`
                      )
                    }
                    className="flex-1 py-2 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium inline-flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    <span>Generate Investigation Report</span>
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-1.5">
                  {[1, 2, 3].map((h) => (
                    <button
                      key={h}
                      onClick={() => handleExpandEgo(entityDetail.entity_id, h)}
                      className="py-1.5 px-2 rounded border border-slate-300 dark:border-slate-700 hover:border-blue-500 font-mono text-[11px] inline-flex items-center justify-center gap-1"
                    >
                      <GitBranch className="w-3 h-3 text-blue-400" />
                      <span>{h}-Hop Ego</span>
                    </button>
                  ))}
                </div>

                {/* Risk Score & Explainable Contributions */}
                {entityDetail.risk?.risk_score !== undefined && (
                  <div className="p-3 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#131C2E] space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        Hybrid Risk Assessment
                      </span>
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={entityDetail.risk.priority} />
                        <span className="font-mono text-base font-bold">
                          {entityDetail.risk.risk_score}/100
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2">
                      {(entityDetail.risk.contributions || []).map((c) => (
                        <div key={c.factor}>
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-600 dark:text-slate-300">{c.factor}</span>
                            <span className="font-mono text-slate-500">
                              +{c.weighted_points} pts ({c.raw_score}/100)
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded bg-slate-200 dark:bg-slate-800 mt-0.5 overflow-hidden">
                            <div
                              className="h-full bg-blue-500"
                              style={{ width: `${Math.min(100, c.raw_score)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Topology & Flow Metrics */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800">
                    <div className="text-[10px] text-slate-500 uppercase">Total Inflow</div>
                    <div className="font-mono font-semibold text-sm mt-0.5 text-emerald-500">
                      {formatUSD(entityDetail.profile?.in_amount)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      In-Degree: {entityDetail.centrality.in_degree}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800">
                    <div className="text-[10px] text-slate-500 uppercase">Total Outflow</div>
                    <div className="font-mono font-semibold text-sm mt-0.5 text-orange-400">
                      {formatUSD(entityDetail.profile?.out_amount)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Out-Degree: {entityDetail.centrality.out_degree}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800">
                    <div className="text-[10px] text-slate-500 uppercase">Betweenness</div>
                    <div className="font-mono font-semibold text-xs mt-0.5">
                      {entityDetail.centrality.betweenness_centrality}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800">
                    <div className="text-[10px] text-slate-500 uppercase">Community Cluster</div>
                    <div className="font-mono font-semibold text-xs mt-0.5">
                      {entityDetail.centrality.community_id >= 0
                        ? `Cluster #${entityDetail.centrality.community_id}`
                        : 'Isolated Pair'}
                    </div>
                  </div>
                </div>

                {/* Linked Accounts (when inspecting a DEVICE or IP node) */}
                {entityDetail.linked_accounts.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Accounts Associated With This {entityDetail.entity_type} (
                      {entityDetail.linked_accounts.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {entityDetail.linked_accounts.map((acc) => (
                        <button
                          key={acc}
                          onClick={() => handleExpandEgo(acc, 2)}
                          className="px-2 py-1 rounded font-mono text-[11px] bg-slate-100 dark:bg-slate-800 hover:border-blue-500 border border-slate-300 dark:border-slate-700"
                        >
                          {formatShortEntity(acc)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Detected Patterns */}
                {(entityDetail.detections || []).length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-red-500" />
                      <span>Detected Network Patterns ({entityDetail.detections?.length})</span>
                    </div>
                    {entityDetail.detections!.map((d) => (
                      <div
                        key={d.detection_id}
                        className="p-2.5 rounded border border-red-500/25 bg-red-500/5 space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <PatternBadge type={d.pattern_type} />
                          <span className="font-mono font-bold text-red-400">
                            {d.risk_score}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
                          {d.summary}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Shared Devices & Shared IPs */}
                {(entityDetail.devices.length > 0 || entityDetail.ips.length > 0) && (
                  <div className="space-y-2">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Device & IP Session Associations
                    </div>
                    {entityDetail.devices.map((dev) => (
                      <div
                        key={dev.device_id}
                        className="p-2 rounded border border-slate-200 dark:border-slate-800 flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 font-mono font-semibold text-orange-500">
                            <Cpu className="w-3.5 h-3.5" />
                            {dev.label}
                          </span>
                          {dev.is_shared && (
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-400">
                              SHARED ({dev.co_using_accounts.length + 1} ACCTS)
                            </span>
                          )}
                        </div>
                        {dev.co_using_accounts.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {dev.co_using_accounts.map((ca) => (
                              <button
                                key={ca}
                                onClick={() => handleExpandEgo(ca, 2)}
                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-500 hover:underline"
                              >
                                {formatShortEntity(ca)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}

                    {entityDetail.ips.map((ip) => (
                      <div
                        key={ip.ip_id}
                        className="p-2 rounded border border-slate-200 dark:border-slate-800 flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 font-mono font-semibold text-purple-400">
                            <Globe className="w-3.5 h-3.5" />
                            {ip.label}
                          </span>
                          {ip.is_shared && (
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300">
                              SHARED ({ip.co_using_accounts.length + 1} ACCTS)
                            </span>
                          )}
                        </div>
                        {ip.co_using_accounts.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {ip.co_using_accounts.map((ca) => (
                              <button
                                key={ca}
                                onClick={() => handleExpandEgo(ca, 2)}
                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-500 hover:underline"
                              >
                                {formatShortEntity(ca)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Incoming & Outgoing Counterparties */}
                {(entityDetail.incoming_counterparties.length > 0 ||
                  entityDetail.outgoing_counterparties.length > 0) && (
                  <div className="grid grid-cols-1 gap-2">
                    {entityDetail.incoming_counterparties.length > 0 && (
                      <div>
                        <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">
                          Incoming Senders ({entityDetail.incoming_counterparties.length})
                        </div>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {entityDetail.incoming_counterparties.map((cp) => (
                            <div
                              key={cp.entity_id}
                              onClick={() => handleExpandEgo(cp.entity_id, 2)}
                              className="px-2 py-1 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex justify-between cursor-pointer hover:border-blue-500"
                            >
                              <span className="font-mono text-blue-500">← {cp.label}</span>
                              <span className="font-mono">
                                {formatUSD(cp.total_amount)} ({cp.tx_count})
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {entityDetail.outgoing_counterparties.length > 0 && (
                      <div>
                        <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">
                          Outgoing Recipients ({entityDetail.outgoing_counterparties.length})
                        </div>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {entityDetail.outgoing_counterparties.map((cp) => (
                            <div
                              key={cp.entity_id}
                              onClick={() => handleExpandEgo(cp.entity_id, 2)}
                              className="px-2 py-1 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex justify-between cursor-pointer hover:border-blue-500"
                            >
                              <span className="font-mono text-orange-400">→ {cp.label}</span>
                              <span className="font-mono">
                                {formatUSD(cp.total_amount)} ({cp.tx_count})
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Recent Ledger Transactions */}
                {entityDetail.recent_transactions.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Supporting Ledger Transfers
                    </div>
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {entityDetail.recent_transactions.slice(0, 10).map((tx) => (
                        <div
                          key={tx.transaction_id}
                          className="p-2 rounded border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 text-[11px] font-mono"
                        >
                          <div className="flex justify-between font-semibold">
                            <span>{tx.transaction_id}</span>
                            <span>{formatUSD(tx.amount)}</span>
                          </div>
                          <div className="text-slate-500 truncate">
                            {tx.sender_account} → {tx.receiver_account}
                          </div>
                          <div className="text-[10px] text-slate-400 flex justify-between mt-0.5">
                            <span>{formatTimestamp(tx.timestamp)}</span>
                            <span>IForest: {tx.ml_anomaly_score ?? 0}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
};

