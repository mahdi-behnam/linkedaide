import React, { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { useTheme } from "../context/ThemeContext";
import { StatusPill } from "../components/StatusPill";
import { ToastContainer } from "../components/toast/ToastContainer";
import { formatKeyCombo, isMac } from "../utils/platform";
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
  PencilSimple,
  Calendar,
  UserPlus,
  ChartLineUp,
  MagnifyingGlass,
  Sun,
  Moon,
  IconProps,
} from "../components/icons";
import { CommandPalette } from "../components/CommandPalette";
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
    connectionQueue,
    notifications,
    removeNotification,
  } = useApp();

  const { resolvedTheme, toggleTheme } = useTheme();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [navHistory, setNavHistory] = useState<NavigationTab[]>([currentTab]);
  const [historyIndex, setHistoryIndex] = useState<number>(0);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  const navigateToTab = (tab: NavigationTab) => {
    if (tab === currentTab) return;
    const newHistory = navHistory.slice(0, historyIndex + 1);
    newHistory.push(tab);
    setNavHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setCurrentTab(tab);
  };

  const handleBack = () => {
    if (historyIndex > 0) {
      const prevIndex = historyIndex - 1;
      setHistoryIndex(prevIndex);
      setCurrentTab(navHistory[prevIndex]);
    }
  };

  const handleForward = () => {
    if (historyIndex < navHistory.length - 1) {
      const nextIndex = historyIndex + 1;
      setHistoryIndex(nextIndex);
      setCurrentTab(navHistory[nextIndex]);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
          className={`flex items-center pb-2 px-3.5 ${
            isMac
              ? isCollapsed
                ? "pt-8 justify-center"
                : "pt-3 justify-end"
              : isCollapsed
              ? "pt-3 justify-center"
              : "pt-3 justify-end"
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
            className="relative flex h-7 w-7 shrink-0 items-center justify-center transition-transform hover:scale-105"
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
              className="h-full w-full object-contain select-none"
            />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="truncate text-xs font-semibold text-on-surface">
                LinkedAide
              </span>
              <span className="truncate text-[10px] text-on-surface-variant">
                Control Center
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
                onClick={() => navigateToTab(item.id)}
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
      </aside>

      {/* Main Container */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Control Bar */}
        <header
          data-testid="top-bar"
          style={dragRegion}
          className={`flex h-11 items-center justify-between border-b border-outline bg-surface-container-low/80 pl-4 ${
            isMac ? "pr-4" : "pr-[140px]"
          } backdrop-blur-md`}
        >
          {/* Left Controls & Search */}
          <div className="flex items-center gap-2.5" style={noDragRegion}>
            {/* History Navigation Arrows */}
            <div className="flex items-center gap-0.5 text-on-surface-variant">
              <button
                type="button"
                data-testid="nav-back-btn"
                aria-label="Back"
                disabled={historyIndex <= 0}
                onClick={handleBack}
                className={`flex h-6 w-6 items-center justify-center rounded-md transition-colors ${
                  historyIndex > 0
                    ? "hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface cursor-pointer"
                    : "opacity-30 cursor-not-allowed text-on-surface-variant"
                }`}
              >
                <CaretLeft size={13} weight="bold" />
              </button>
              <button
                type="button"
                data-testid="nav-forward-btn"
                aria-label="Forward"
                disabled={historyIndex >= navHistory.length - 1}
                onClick={handleForward}
                className={`flex h-6 w-6 items-center justify-center rounded-md transition-colors ${
                  historyIndex < navHistory.length - 1
                    ? "hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface cursor-pointer"
                    : "opacity-30 cursor-not-allowed text-on-surface-variant"
                }`}
              >
                <CaretRight size={13} weight="bold" />
              </button>
            </div>

            {/* ⌘K Search Bar */}
            <button
              type="button"
              data-testid="search-bar-trigger"
              onClick={() => setIsCommandPaletteOpen(true)}
              className="flex items-center gap-2 rounded-md border border-outline bg-surface-container-lowest px-2.5 py-1 text-xs text-on-surface-variant shadow-2xs transition-colors hover:border-outline-variant w-64 text-left cursor-pointer"
            >
              <MagnifyingGlass size={13} className="text-on-surface-variant shrink-0" />
              <span className="truncate text-[11px] flex-1">Search views, actions...</span>
              <kbd className="hidden sm:inline-block rounded border border-outline/50 px-1 text-[10px] font-mono text-on-surface-variant bg-surface-container-low">
                {formatKeyCombo("K")}
              </kbd>
            </button>
          </div>

          {/* Right Status & Controls */}
          <div className="flex items-center gap-2" style={noDragRegion}>
            {/* System Status Pill (Shown only when non-operational/tripped) */}
            {systemStatus !== "operational" && <StatusPill status={systemStatus} size="sm" />}

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
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto bg-surface p-5">
          {children}
        </main>

        {/* Stackable In-App Toast Notifications */}
        <ToastContainer toasts={notifications} onDismiss={removeNotification} />

        {/* ⌘K Command Palette Modal */}
        <CommandPalette
          isOpen={isCommandPaletteOpen}
          onClose={() => setIsCommandPaletteOpen(false)}
          onSelectTab={navigateToTab}
          onTogglePause={togglePause}
          isPaused={isPaused}
          onToggleTheme={toggleTheme}
          currentTheme={resolvedTheme}
        />
      </div>
    </div>
  );
};
