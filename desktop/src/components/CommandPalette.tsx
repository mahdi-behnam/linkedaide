import React, { useState, useEffect, useMemo, useRef } from "react";
import { NavigationTab } from "../types";
import {
  House,
  Inbox,
  ShieldCheck,
  ClockCounterClockwise,
  Stethoscope,
  SlidersHorizontal,
  PencilSimple,
  Calendar,
  UserPlus,
  ChartLineUp,
  MagnifyingGlass,
  Play,
  Pause,
  Sun,
  Moon,
  IconProps,
} from "./icons";

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: NavigationTab) => void;
  onTogglePause?: () => void;
  isPaused?: boolean;
  onToggleTheme?: () => void;
  currentTheme?: string;
}

interface PaletteItem {
  id: string;
  title: string;
  subtitle: string;
  category: "Navigation" | "Actions";
  icon: React.ComponentType<IconProps>;
  action: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectTab,
  onTogglePause,
  isPaused = false,
  onToggleTheme,
  currentTheme = "light",
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const allItems: PaletteItem[] = useMemo(() => {
    const navItems: PaletteItem[] = [
      {
        id: "tab-dashboard",
        title: "Dashboard",
        subtitle: "Operations overview and realtime system telemetry",
        category: "Navigation",
        icon: House,
        action: () => {
          onSelectTab("dashboard");
          onClose();
        },
      },
      {
        id: "tab-queue",
        title: "Approval Queue",
        subtitle: "Review and approve pending comment suggestions",
        category: "Navigation",
        icon: Inbox,
        action: () => {
          onSelectTab("queue");
          onClose();
        },
      },
      {
        id: "tab-outreach",
        title: "Outreach Queue",
        subtitle: "Review personalized connection requests and notes",
        category: "Navigation",
        icon: UserPlus,
        action: () => {
          onSelectTab("outreach");
          onClose();
        },
      },
      {
        id: "tab-composer",
        title: "Post Composer Studio",
        subtitle: "Draft, hook craft, and schedule LinkedIn posts",
        category: "Navigation",
        icon: PencilSimple,
        action: () => {
          onSelectTab("composer");
          onClose();
        },
      },
      {
        id: "tab-calendar",
        title: "Content Calendar",
        subtitle: "Weekly and monthly scheduled content roadmap",
        category: "Navigation",
        icon: Calendar,
        action: () => {
          onSelectTab("calendar");
          onClose();
        },
      },
      {
        id: "tab-analytics",
        title: "Growth Analytics",
        subtitle: "Track impressions, engagements, and follower growth",
        category: "Navigation",
        icon: ChartLineUp,
        action: () => {
          onSelectTab("analytics");
          onClose();
        },
      },
      {
        id: "tab-vault",
        title: "LinkedIn Vault",
        subtitle: "Manage Playwright session credentials & Fernet keys",
        category: "Navigation",
        icon: ShieldCheck,
        action: () => {
          onSelectTab("vault");
          onClose();
        },
      },
      {
        id: "tab-history",
        title: "Audit History",
        subtitle: "Immutable audit log of all executed and rejected actions",
        category: "Navigation",
        icon: ClockCounterClockwise,
        action: () => {
          onSelectTab("history");
          onClose();
        },
      },
      {
        id: "tab-doctor",
        title: "System Diagnostics",
        subtitle: "Subsystem health checks and Python CLI doctor suite",
        category: "Navigation",
        icon: Stethoscope,
        action: () => {
          onSelectTab("doctor");
          onClose();
        },
      },
      {
        id: "tab-settings",
        title: "Settings",
        subtitle: "Configure runtime thresholds, quotas, and worker secrets",
        category: "Navigation",
        icon: SlidersHorizontal,
        action: () => {
          onSelectTab("settings");
          onClose();
        },
      },
    ];

    const actionItems: PaletteItem[] = [
      {
        id: "act-pause",
        title: isPaused ? "Resume Agent Operations" : "Pause Agent Operations",
        subtitle: isPaused
          ? "Resume automated feed scouting and action dispatching"
          : "Temporarily suspend automated workflows and execution",
        category: "Actions",
        icon: isPaused ? Play : Pause,
        action: () => {
          onTogglePause?.();
          onClose();
        },
      },
      {
        id: "act-theme",
        title: currentTheme === "dark" ? "Switch to Light Theme" : "Switch to Dark Theme",
        subtitle: `Currently using ${currentTheme} mode`,
        category: "Actions",
        icon: currentTheme === "dark" ? Sun : Moon,
        action: () => {
          onToggleTheme?.();
          onClose();
        },
      },
    ];

    return [...navItems, ...actionItems];
  }, [isPaused, currentTheme, onSelectTab, onClose, onTogglePause, onToggleTheme]);

  const filteredItems = useMemo(() => {
    if (!query.trim()) return allItems;
    const q = query.toLowerCase().trim();
    return allItems.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.subtitle.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
    );
  }, [allItems, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredItems]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (filteredItems.length > 0 ? (prev + 1) % filteredItems.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredItems.length > 0 ? (prev - 1 + filteredItems.length) % filteredItems.length : 0
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        filteredItems[selectedIndex].action();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      data-testid="command-palette-backdrop"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-xs pt-20 px-4 animate-in fade-in duration-100"
    >
      <div
        data-testid="command-palette"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-outline bg-surface-container-low shadow-2xl transition-all"
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-2.5 border-b border-outline px-4 py-3 bg-surface-container-lowest">
          <MagnifyingGlass size={16} className="text-on-surface-variant shrink-0" />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a view name, action, or command..."
            className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden"
          />
          <kbd className="hidden sm:inline-block rounded-md border border-outline px-1.5 py-0.5 text-[10px] font-mono text-on-surface-variant bg-surface-container-low">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-1.5 space-y-0.5">
          {filteredItems.length === 0 ? (
            <div className="p-6 text-center text-xs text-on-surface-variant">
              No matching views or commands found for &quot;{query}&quot;
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  data-testid={`palette-item-${item.id}`}
                  onClick={item.action}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors text-xs ${
                    isSelected
                      ? "bg-surface-container-highest text-on-surface font-medium"
                      : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                  }`}
                >
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-md ${
                      isSelected
                        ? "bg-primary text-on-primary"
                        : "bg-surface-container text-on-surface-variant"
                    }`}
                  >
                    <Icon size={14} weight={isSelected ? "bold" : "regular"} />
                  </div>
                  <div className="flex flex-col flex-1 overflow-hidden">
                    <span className="truncate text-on-surface font-medium">{item.title}</span>
                    <span className="truncate text-[10px] text-on-surface-variant">
                      {item.subtitle}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-outline/40 text-on-surface-variant">
                    {item.category}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts hint */}
        <div className="flex items-center justify-between border-t border-outline bg-surface-container-lowest px-4 py-2 text-[10px] text-on-surface-variant">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="font-mono font-semibold">↑↓</kbd> navigate
            </span>
            <span>
              <kbd className="font-mono font-semibold">↵</kbd> select
            </span>
          </div>
          <span>⌘K Spotlight</span>
        </div>
      </div>
    </div>
  );
};
