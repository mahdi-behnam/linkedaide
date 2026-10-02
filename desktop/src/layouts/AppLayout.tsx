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
  PencilSimple,
  Calendar,
  UserPlus,
  ChartLineUp,
  MagnifyingGlass,
  Sun,
  Moon,
  IconProps,
} from "../components/icons";
import roundActiveIcon from "../assets/icons/round-active.png";
import roundStandbyIcon from "../assets/icons/round-standby.png";
import roundAttentionIcon from "../assets/icons/round-attention.png";

interface AppLayoutProps {
  children?: React.ReactNode;
}

interface NavItem {
  id: NavigationTab;
  label: string;
  icon: React.ComponentType<IconProps>;
  badge?: number;
}

const dragRegion = { WebkitAppRegion: "drag" } as unknown as React.CSSProperties;
const noDragRegion = { WebkitAppRegion: "no-drag" } as unknown as React.CSSProperties;

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
        <div
          className={`flex items-center pt-3 pb-2 px-3.5 ${
            isCollapsed ? "justify-center" : "justify-end"
          }`}
          style={dragRegion}
        >
          <button
            data-testid="collapse-toggle"
            type="button"
            style={noDragRegion}
            onClick={() => setIsCollapsed((prev) => !prev)}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-5 w-5 items-center justify-center rounded-md border border-outline bg-surface-container-lowest text-on-surface-variant transition-colors hover:text-on-surface hover:bg-surface-container-high active:scale-95 shadow-2xs"
          >
            {isCollapsed ? <CaretRight size={11} /> : <CaretLeft size={11} />}
          </button>
        </div>

        {/* Workspace Brand Header */}
        <div className="flex items-center gap-2.5 border-b border-outline px-3.5 pb-2.5 pt-0.5">
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full overflow-hidden shadow-2xs transition-transform hover:scale-105"
            title={
              isPaused
                ? "LinkedAide: Standby Mode"
                : pendingCount > 0
                ? `LinkedAide: ${pendingCount} Action${pendingCount > 1 ? "s" : ""} Pending Review`
                : "LinkedAide: Active & Monitoring"
            }
          >
            <img
              src={
                isPaused
                  ? roundStandbyIcon
                  : pendingCount > 0
                  ? roundAttentionIcon
                  : roundActiveIcon
              }
              alt="LinkedAide"
              className="h-full w-full object-cover"
            />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="truncate text-xs font-semibold text-on-surface">
                LinkedAide
              </span>
              <span className="truncate text-[10px] text-on-surface-variant">
                HITL Cockpit
              </span>
            </div>
          )}
        </div>

        {/* Navigation Tab List */}
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-1.5">
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
                className={`group relative flex w-full items-center text-xs transition-colors duration-100 active:scale-[0.99] ${
                  isCollapsed ? "justify-center p-2 rounded-md" : "gap-2.5 px-2.5 py-1.5 rounded-md"
                } ${
                  isActive
                    ? "bg-surface-container-highest text-on-surface font-medium shadow-2xs"
                    : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                }`}
              >
                <Icon
                  size={16}
                  weight={isActive ? "bold" : "regular"}
                  className={`shrink-0 transition-colors ${
                    isActive ? "text-primary" : "text-on-surface-variant group-hover:text-on-surface"
                  }`}
                />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
                {!isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-auto font-sans text-[11px] font-medium text-amber-600 dark:text-amber-400 tabular-nums">
                    {item.badge}
                  </span>
                )}
                {isCollapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute top-1 right-1 font-sans text-[9px] font-bold text-amber-500 tabular-nums">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Persistent Bottom Bar: KV Edge Sync Status Widget */}
        <div className="border-t border-outline p-2">
          {!isCollapsed ? (
            <div className="flex items-center justify-between rounded-md border border-outline bg-surface-container-lowest px-2.5 py-1.5 shadow-2xs">
              <div className="flex flex-col">
                <span className="text-[11px] font-medium text-on-surface">KV Edge Synced</span>
                <span className="text-[10px] text-on-surface-variant">Edge Relay Connected</span>
              </div>
            </div>
          ) : (
            <div className="flex justify-center py-1" title="KV Edge Synced · Edge Relay Connected">
              <Globe size={14} className="text-tertiary" />
            </div>
          )}
        </div>
      </aside>

      {/* Main Container */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Control Bar */}
        <header
          data-testid="top-bar"
          style={dragRegion}
          className="flex h-11 items-center justify-between border-b border-outline bg-surface-container-low/80 px-4 backdrop-blur-md"
        >
          {/* Left Controls & Search */}
          <div className="flex items-center gap-2.5" style={noDragRegion}>
            {/* History Navigation Arrows */}
            <div className="flex items-center gap-0.5 text-on-surface-variant">
              <button
                type="button"
                aria-label="Back"
                className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-on-surface"
              >
                <CaretLeft size={13} weight="bold" />
              </button>
              <button
                type="button"
                aria-label="Forward"
                className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-on-surface"
              >
                <CaretRight size={13} weight="bold" />
              </button>
            </div>

            {/* ⌘K Search Bar */}
            <div className="flex items-center gap-2 rounded-md border border-outline bg-surface-container-lowest px-2.5 py-1 text-xs text-on-surface-variant shadow-2xs transition-colors hover:border-outline-variant w-64">
              <MagnifyingGlass size={13} className="text-on-surface-variant shrink-0" />
              <span className="truncate text-[11px]">Search metrics, logs... (⌘K)</span>
            </div>

            {/* Worker Endpoint */}
            <div className="hidden lg:flex items-center gap-1.5 text-xs text-on-surface-variant font-mono">
              <Globe size={13} className="text-on-surface-variant shrink-0" />
              <span className="text-on-surface truncate max-w-[180px] text-[11px]">{telemetry.workerUrl}</span>
              <span className="font-sans text-[10px] font-medium text-tertiary">({telemetry.workerStatus})</span>
            </div>
          </div>

          {/* Right Status & Controls */}
          <div className="flex items-center gap-2" style={noDragRegion}>
            {/* System Status Pill */}
            <StatusPill status={systemStatus} size="sm" />

            {/* Pending Approvals Live Badge */}
            <button
              type="button"
              data-testid="pending-badge-button"
              onClick={() => setCurrentTab("queue")}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-amber-600 dark:text-amber-400 hover:bg-surface-container-high transition-colors"
            >
              <Inbox size={13} weight="bold" />
              <span className="tabular-nums">{pendingCount} Pending</span>
            </button>

            {/* Global Pause Switch */}
            <button
              type="button"
              data-testid="global-pause-button"
              onClick={togglePause}
              className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-all duration-100 active:scale-[0.99] shadow-2xs ${
                isPaused
                  ? "border-amber-500/35 bg-amber-500/15 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25"
                  : "border-outline bg-surface-container-highest text-on-surface hover:bg-surface-container-high"
              }`}
            >
              {isPaused ? (
                <>
                  <Play size={12} weight="fill" className="text-amber-500" />
                  <span>Resume Agent</span>
                </>
              ) : (
                <>
                  <Pause size={12} weight="fill" className="text-on-surface-variant" />
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
              className="flex h-7 w-7 items-center justify-center rounded-md border border-outline bg-surface-container-lowest text-on-surface-variant shadow-2xs transition-colors hover:bg-surface-container-high hover:text-on-surface active:scale-95"
            >
              {resolvedTheme === "dark" ? (
                <Sun size={13} weight="bold" className="text-amber-400" />
              ) : (
                <Moon size={13} weight="bold" className="text-secondary" />
              )}
            </button>

            {/* Profile Avatar */}
            <div
              data-testid="profile-avatar"
              className="flex h-7 w-7 items-center justify-center rounded-md border border-outline bg-surface-container-high text-[11px] font-medium text-on-surface shadow-2xs"
            >
              <span>HA</span>
            </div>
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto bg-surface p-5">
          {children}
        </main>

        {/* Realtime Floating Toast Notification */}
        {lastTriggerMessage && (
          <div
            data-testid="realtime-toast"
            className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-lg border border-outline bg-surface-bright/95 px-3 py-2 text-xs font-medium text-on-surface shadow-md backdrop-blur-md"
          >
            <span>{lastTriggerMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
};
