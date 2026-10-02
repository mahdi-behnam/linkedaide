import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { useTheme } from "../context/ThemeContext";
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
  PencilSimple,
  Calendar,
  UserPlus,
  ChartLineUp,
  MagnifyingGlass,
  Sun,
  Moon,
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
    connectionQueue,
    lastTriggerMessage,
  } = useApp();

  const { resolvedTheme, toggleTheme } = useTheme();

  const [isCollapsed, setIsCollapsed] = useState(false);

  const pendingOutreachCount = connectionQueue
    ? connectionQueue.filter((c) => c.status === "pending").length
    : 0;

  const navItems: NavItem[] = [
    { id: "dashboard", label: "Dashboard", icon: House },
    { id: "queue", label: "Approval Queue", icon: Inbox, badge: pendingCount },
    { id: "outreach", label: "Outreach Queue", icon: UserPlus, badge: pendingOutreachCount },
    { id: "composer", label: "Post Composer", icon: PencilSimple },
    { id: "calendar", label: "Content Calendar", icon: Calendar },
    { id: "analytics", label: "Growth Analytics", icon: ChartLineUp },
    { id: "vault", label: "LinkedIn Vault", icon: ShieldCheck },
    { id: "history", label: "Audit History", icon: ClockCounterClockwise },
    { id: "doctor", label: "Diagnostics", icon: Stethoscope },
    { id: "settings", label: "Settings", icon: SlidersHorizontal },
  ];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface text-on-surface antialiased select-none font-body-md">
      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        className={`relative flex flex-col border-r border-outline bg-surface-container-low transition-all duration-200 ease-out ${
          isCollapsed ? "w-16" : "w-60"
        }`}
      >
        {/* macOS Traffic Lights Window Dots */}
        <div className="flex items-center justify-between px-3.5 pt-3.5 pb-2">
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-[#ff5f56] border border-black/10 inline-block shadow-2xs" />
            <span className="h-3 w-3 rounded-full bg-[#ffbd2e] border border-black/10 inline-block shadow-2xs" />
            <span className="h-3 w-3 rounded-full bg-[#27c93f] border border-black/10 inline-block shadow-2xs" />
          </div>
          <button
            data-testid="collapse-toggle"
            type="button"
            onClick={() => setIsCollapsed((prev) => !prev)}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-6 w-6 items-center justify-center rounded-lg border border-outline bg-surface-container-lowest text-on-surface-variant transition-colors hover:text-on-surface hover:bg-surface-container-high active:scale-95 shadow-2xs"
          >
            {isCollapsed ? <CaretRight size={13} /> : <CaretLeft size={13} />}
          </button>
        </div>

        {/* Workspace Brand Header */}
        <div className="flex items-center gap-2.5 border-b border-outline px-3.5 pb-3 pt-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary shadow-xs">
            <Lightning size={17} weight="bold" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="truncate text-xs font-semibold tracking-wider text-on-surface uppercase">
                HITL Cockpit
              </span>
              <span className="truncate font-mono text-[10px] text-on-surface-variant">
                LinkedIn Safe Agent
              </span>
            </div>
          )}
        </div>

        {/* Navigation Tab List */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
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
                className={`group relative flex w-full items-center text-xs transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
                  isCollapsed ? "justify-center p-2.5 rounded-xl" : "gap-3 px-3 py-2 rounded-xl"
                } ${
                  isActive
                    ? "bg-surface-container-highest text-on-surface font-body-strong shadow-xs"
                    : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
                }`}
              >
                <Icon
                  size={18}
                  weight={isActive ? "bold" : "regular"}
                  className={`shrink-0 transition-colors ${
                    isActive ? "text-primary" : "text-on-surface-variant group-hover:text-on-surface"
                  }`}
                />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
                {!isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-auto rounded-full border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-amber-500">
                    {item.badge}
                  </span>
                )}
                {isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-amber-500" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Persistent Bottom Bar: KV Edge Sync Status Widget */}
        <div className="border-t border-outline p-2.5">
          {!isCollapsed ? (
            <div className="flex items-center justify-between rounded-xl border border-outline bg-surface-container-lowest p-2 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-tertiary opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-tertiary" />
                </span>
                <div className="flex flex-col">
                  <span className="text-[11px] font-medium text-on-surface">KV Edge Synced</span>
                  <span className="text-[9px] text-on-surface-variant">Connected pulse</span>
                </div>
              </div>
              <span className="rounded-full bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-tertiary uppercase">
                Active
              </span>
            </div>
          ) : (
            <div className="flex justify-center py-1">
              <span className="relative flex h-2.5 w-2.5" title="KV Edge Synced · Connected pulse">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-tertiary opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-tertiary" />
              </span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Container */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Control Bar */}
        <header
          data-testid="top-bar"
          className="flex h-14 items-center justify-between border-b border-outline bg-surface-container-low/70 px-6 backdrop-blur-md"
        >
          {/* Left Controls & Search */}
          <div className="flex items-center gap-3">
            {/* History Navigation Arrows */}
            <div className="flex items-center gap-0.5 text-on-surface-variant">
              <button
                type="button"
                aria-label="Back"
                className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-on-surface"
              >
                <CaretLeft size={14} weight="bold" />
              </button>
              <button
                type="button"
                aria-label="Forward"
                className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-on-surface"
              >
                <CaretRight size={14} weight="bold" />
              </button>
            </div>

            {/* ⌘K Search Bar */}
            <div className="flex items-center gap-2 rounded-xl border border-outline bg-surface-container-lowest px-3 py-1.5 text-xs text-on-surface-variant shadow-xs transition-colors hover:border-outline-variant w-72">
              <MagnifyingGlass size={14} className="text-on-surface-variant shrink-0" />
              <span className="truncate">Search metrics, logs, or actions... (⌘K)</span>
            </div>

            {/* Worker Endpoint Chip */}
            <div className="hidden lg:flex items-center gap-2 rounded-xl border border-outline bg-surface-container-lowest px-2.5 py-1 text-xs shadow-xs">
              <Globe size={13} className="text-on-surface-variant shrink-0" />
              <div className="flex items-center gap-1.5 font-mono text-[11px]">
                <span className="h-1.5 w-1.5 rounded-full bg-tertiary" />
                <span className="text-on-surface">{telemetry.workerUrl}</span>
              </div>
              <span className="rounded-full bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.2 font-mono text-[9px] font-semibold text-tertiary uppercase">
                {telemetry.workerStatus}
              </span>
            </div>
          </div>

          {/* Right Status & Controls */}
          <div className="flex items-center gap-2.5">
            {/* System Status Pill */}
            <StatusPill status={systemStatus} size="sm" />

            {/* Pending Approvals Live Badge */}
            <button
              type="button"
              data-testid="pending-badge-button"
              onClick={() => setCurrentTab("queue")}
              className="flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-500 transition-colors hover:bg-amber-500/20 active:translate-y-[1px] active:scale-[0.98] shadow-xs"
            >
              <Inbox size={14} weight="bold" />
              <span>{pendingCount} Pending</span>
            </button>

            {/* Global Pause Switch */}
            <button
              type="button"
              data-testid="global-pause-button"
              onClick={togglePause}
              className={`flex items-center gap-2 rounded-xl border px-3 py-1 text-xs font-semibold tracking-wide uppercase transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] shadow-xs ${
                isPaused
                  ? "border-amber-500/40 bg-amber-500/20 text-amber-500 hover:bg-amber-500/30"
                  : "border-outline bg-surface-container-highest text-on-surface hover:bg-surface-container-high"
              }`}
            >
              {isPaused ? (
                <>
                  <Play size={13} weight="fill" className="text-amber-500" />
                  <span>Resume Agent</span>
                </>
              ) : (
                <>
                  <Pause size={13} weight="fill" className="text-on-surface-variant" />
                  <span>Pause Agent</span>
                </>
              )}
            </button>

            {/* Theme Toggle Button */}
            <button
              type="button"
              data-testid="theme-toggle-button"
              onClick={toggleTheme}
              title={`Switch to ${resolvedTheme === "dark" ? "Light" : "Dark"} mode`}
              aria-label="Toggle theme"
              className="flex h-8 w-8 items-center justify-center rounded-xl border border-outline bg-surface-container-lowest text-on-surface-variant shadow-xs transition-colors hover:bg-surface-container-high hover:text-on-surface active:scale-95"
            >
              {resolvedTheme === "dark" ? (
                <Sun size={15} weight="bold" className="text-amber-400" />
              ) : (
                <Moon size={15} weight="bold" className="text-secondary" />
              )}
            </button>

            {/* Profile Avatar */}
            <div
              data-testid="profile-avatar"
              className="flex h-8 w-8 items-center justify-center rounded-xl border border-outline bg-surface-container-high text-xs font-bold text-on-surface shadow-xs"
            >
              <span>HA</span>
            </div>
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto bg-surface p-6">
          {children}
        </main>

        {/* Realtime Floating Toast Notification */}
        {lastTriggerMessage && (
          <div
            data-testid="realtime-toast"
            className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 rounded-xl border border-tertiary/40 bg-surface-container-lowest px-4 py-2.5 text-xs font-medium text-tertiary shadow-xl backdrop-blur-md"
          >
            <span className="flex h-2 w-2 rounded-full bg-tertiary" />
            <span className="text-on-surface">{lastTriggerMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
};
