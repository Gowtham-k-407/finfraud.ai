import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Database,
  FileSearch,
  LayoutDashboard,
  Menu,
  Moon,
  Network,
  Search,
  ShieldAlert,
  Sun,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';

const NAV_ITEMS = [
  { to: '/', label: 'Command Centre', icon: LayoutDashboard, exact: true },
  { to: '/network', label: 'Network Explorer', icon: Network },
  { to: '/investigations', label: 'Investigation Workspace', icon: FileSearch },
  { to: '/transactions', label: 'Transaction Intelligence', icon: Activity },
  { to: '/cases', label: 'Cases & Audit Trail', icon: Briefcase },
  { to: '/data', label: 'Data & Model Health', icon: Database },
];

export const WorkstationShell: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [quickQuery, setQuickQuery] = useState('');
  const [health, setHealth] = useState<any>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [dark]);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'offline' }));
  }, [location.pathname]);

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = quickQuery.trim();
    if (!q) return;
    navigate(`/network?focus=${encodeURIComponent(q)}`);
    setQuickQuery('');
  };

  const currentNav =
    NAV_ITEMS.find((item) =>
      item.exact ? location.pathname === item.to : location.pathname.startsWith(item.to)
    ) || NAV_ITEMS[0];

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#090D16] text-slate-900 dark:text-slate-100">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed lg:static inset-y-0 left-0 z-50 flex flex-col border-r border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#0C121E] transition-all duration-200',
          collapsed ? 'w-[68px]' : 'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Brand Header */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-slate-200 dark:border-slate-800/90">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded bg-red-600/15 border border-red-500/40 flex items-center justify-center shrink-0">
              <ShieldAlert className="w-4 h-4 text-red-500" />
            </div>
            {!collapsed && (
              <div className="leading-tight">
                <div className="font-mono font-bold text-sm tracking-wider text-slate-900 dark:text-white">
                  TRACE <span className="text-red-500">//</span> FIU
                </div>
                <div className="text-[10px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-widest">
                  Network Intelligence
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1 text-slate-400 hover:text-slate-200"
            aria-label="Close navigation"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 py-3 px-2.5 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-2.5 py-2 rounded text-xs font-medium transition-colors',
                    isActive
                      ? 'bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 border border-blue-500/25'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100 border border-transparent'
                  )
                }
                title={collapsed ? item.label : undefined}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer Collapse & Compliance Notice */}
        <div className="p-2.5 border-t border-slate-200 dark:border-slate-800/90 space-y-2">
          {!collapsed && (
            <div className="px-2 py-1.5 rounded bg-slate-100 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Human-in-the-loop decision support. Analytical indicators are not proof of criminal guilt.
            </div>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="hidden lg:flex w-full items-center justify-center gap-2 py-1.5 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 rounded hover:bg-slate-100 dark:hover:bg-slate-800/60"
            aria-label="Toggle sidebar width"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            {!collapsed && <span>Collapse Rail</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Shell */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Command Header */}
        <header className="h-14 px-4 lg:px-6 flex items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800/90 bg-white/95 dark:bg-[#0C121E]/95 backdrop-blur sticky top-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-1.5 rounded border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300"
              aria-label="Open menu"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 text-xs font-mono text-slate-500 dark:text-slate-400 truncate">
              <span className="hidden sm:inline">WORKSTATION</span>
              <span className="hidden sm:inline text-slate-400">/</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide truncate">
                {currentNav.label}
              </span>
            </div>
          </div>

          {/* Global Entity / Account Quick Jump */}
          <form onSubmit={handleGlobalSearch} className="hidden md:flex flex-1 max-w-md">
            <div className="relative w-full">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={quickQuery}
                onChange={(e) => setQuickQuery(e.target.value)}
                placeholder="Jump to account, device, or IP (e.g. ACC_MULE_7701, DEV_SHADOW_901)..."
                className="w-full pl-8 pr-3 py-1.5 text-xs font-mono rounded bg-slate-100 dark:bg-[#131C2E] border border-slate-200 dark:border-slate-700/80 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>
          </form>

          {/* Right Status & Theme Controls */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded bg-slate-100 dark:bg-[#131C2E] border border-slate-200 dark:border-slate-800 text-[11px] font-mono">
              <span
                className={clsx(
                  'w-2 h-2 rounded-full',
                  health?.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'
                )}
              />
              <span className="text-slate-600 dark:text-slate-300">
                {health?.active_transactions
                  ? `${health.active_transactions.toLocaleString()} TXs`
                  : 'API SYNC'}
              </span>
              <span className="text-slate-400">|</span>
              <span className="text-blue-600 dark:text-blue-400">
                {health?.ai_engine?.llm_configured ? 'LLM GROUNDED' : 'EVIDENCE ENGINE'}
              </span>
            </div>

            <button
              onClick={() => setDark((d) => !d)}
              className="p-1.5 rounded border border-slate-200 dark:border-slate-700/80 bg-slate-100 dark:bg-[#131C2E] text-slate-700 dark:text-slate-300 hover:border-blue-500 transition-colors"
              title={dark ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
              aria-label="Toggle color theme"
            >
              {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </header>

        {/* Active Page Canvas */}
        <main className="flex-1 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

