import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import { NavigationTab } from "../types";
import {
  House,
  Inbox,
  ShieldCheck,
  ClockCounterClockwise,
  Stethoscope,
  SlidersHorizontal,
  Play,
  Pause,
  CaretLeft,
  CaretRight,
  Globe,
  Lightning,
  IconProps,
} from "../components/icons";

interface AppLayoutProps {
  children?: React.ReactNode;
}

interface NavItem {
  id: NavigationTab;
  label: string;
  icon: React.ComponentType<IconProps>;
  badge?: number;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const {
    currentTab,
    setCurrentTab,
    systemStatus,
    isPaused,
    togglePause,
    pendingCount,
    telemetry,
  } = useApp();

  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems: NavItem[] = [
    { id: "dashboard", label: "Dashboard", icon: House },
    { id: "queue", label: "Approval Queue", icon: Inbox, badge: pendingCount },
    { id: "vault", label: "LinkedIn Vault", icon: ShieldCheck },
    { id: "history", label: "Audit History", icon: ClockCounterClockwise },
    { id: "doctor", label: "Diagnostics", icon: Stethoscope },
    { id: "settings", label: "Settings", icon: SlidersHorizontal },
  ];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 antialiased selection:bg-emerald-500/20 selection:text-emerald-200">
      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        className={`relative flex flex-col border-r border-zinc-800 bg-zinc-900/60 backdrop-blur-md transition-all duration-200 ease-out ${
          isCollapsed ? "w-16" : "w-60"
        }`}
      >
        {/* Workspace Brand Header */}
        <div className="flex h-14 items-center justify-between border-b border-zinc-800/80 px-3">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 shadow-xs">
              <Lightning size={18} weight="bold" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col overflow-hidden">
                <span className="truncate text-xs font-semibold tracking-wider text-zinc-100 uppercase">
                  HITL Cockpit
                </span>
                <span className="truncate font-mono text-[10px] text-zinc-500">
                  LinkedIn Safe Agent
                </span>
              </div>
            )}
          </div>
          <button
            data-testid="collapse-toggle"
            type="button"
            onClick={() => setIsCollapsed((prev) => !prev)}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900/60 text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-100 active:translate-y-[1px] active:scale-[0.98]"
          >
            {isCollapsed ? <CaretRight size={14} /> : <CaretLeft size={14} />}
          </button>
        </div>

        {/* Navigation Tab List */}
        <nav className="flex-1 space-y-1 p-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                data-testid={`nav-${item.id}`}
                type="button"
                onClick={() => setCurrentTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`group relative flex w-full items-center rounded-md text-xs font-medium transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
                  isCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2"
                } ${
                  isActive
                    ? "border border-zinc-700/80 bg-zinc-800/90 text-zinc-100 shadow-xs"
                    : "border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900/80 hover:text-zinc-200"
                }`}
              >
                <Icon
                  size={18}
                  weight={isActive ? "bold" : "regular"}
                  className={`shrink-0 transition-colors ${
                    isActive ? "text-emerald-400" : "text-zinc-400 group-hover:text-zinc-200"
                  }`}
                />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
                {!isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-auto rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-amber-400">
                    {item.badge}
                  </span>
                )}
                {isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-amber-400" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Persistent Bottom Bar */}
        <div className="border-t border-zinc-800/80 p-2.5">
          {!isCollapsed ? (
            <div className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-950/70 p-2 font-mono text-[10px]">
              <div className="flex items-center gap-1.5 text-zinc-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span>KV Edge Sync</span>
              </div>
              <span className="text-zinc-500">HITL-v1</span>
            </div>
          ) : (
            <div className="flex justify-center">
              <span className="h-2 w-2 rounded-full bg-emerald-400" title="KV Edge Sync Active" />
            </div>
          )}
        </div>
      </aside>

      {/* Main Container */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Control Bar */}
        <header
          data-testid="top-bar"
          className="flex h-14 items-center justify-between border-b border-zinc-800 bg-zinc-900/40 px-6 backdrop-blur-md"
        >
          {/* Worker URL Connection Status */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/80 px-2.5 py-1 text-xs">
              <Globe size={14} className="text-zinc-400" />
              <div className="flex items-center gap-1.5 font-mono text-xs">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span className="text-zinc-300">{telemetry.workerUrl}</span>
              </div>
              <span className="rounded bg-emerald-500/10 px-1 py-0.5 font-mono text-[9px] font-medium text-emerald-400 uppercase">
                {telemetry.workerStatus}
              </span>
            </div>
          </div>

          {/* Right Status & Controls */}
          <div className="flex items-center gap-3">
            {/* System Status Pill */}
            <StatusPill status={systemStatus} size="sm" />

            {/* Pending Approvals Live Badge */}
            <button
              type="button"
              data-testid="pending-badge-button"
              onClick={() => setCurrentTab("queue")}
              className="flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300 transition-colors hover:bg-amber-500/20 active:translate-y-[1px] active:scale-[0.98]"
            >
              <Inbox size={14} weight="bold" />
              <span>{pendingCount} Pending</span>
            </button>

            {/* Global Pause Switch */}
            <button
              type="button"
              data-testid="global-pause-button"
              onClick={togglePause}
              className={`flex items-center gap-2 rounded-md border px-3 py-1 text-xs font-semibold tracking-wide uppercase transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
                isPaused
                  ? "border-amber-500/40 bg-amber-500/20 text-amber-300 hover:bg-amber-500/30"
                  : "border-zinc-700 bg-zinc-800/90 text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100"
              }`}
            >
              {isPaused ? (
                <>
                  <Play size={13} weight="fill" className="text-amber-400" />
                  <span>Resume Agent</span>
                </>
              ) : (
                <>
                  <Pause size={13} weight="fill" className="text-zinc-400" />
                  <span>Pause Agent</span>
                </>
              )}
            </button>
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto bg-zinc-950 p-6">
          {children}
        </main>
      </div>
    </div>
  );
};
