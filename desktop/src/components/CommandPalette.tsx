import React, { useState, useEffect, useMemo, useRef } from "react";
import { NavigationTab } from "../types";
import { MagnifyingGlass } from "./icons";
import { formatKeyCombo } from "../utils/platform";
import { useApp } from "../context/AppContext";
import { SearchCategory, SearchDocument } from "../services/search/types";
import { buildSearchIndex } from "../services/search/searchIndexBuilder";
import { searchAndRank } from "../services/search/searchScorer";

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab?: (tab: NavigationTab) => void;
  onTogglePause?: () => void;
  isPaused?: boolean;
  onToggleTheme?: () => void;
  currentTheme?: string;
}

type FilterCategory = "All" | SearchCategory;

const CATEGORY_CHIPS: FilterCategory[] = [
  "All",
  "Navigation",
  "Queue",
  "Outreach",
  "Post",
  "Setting",
  "Diagnostic",
  "Action",
];

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Navigation: {
    bg: "bg-blue-500/10",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-500/20",
  },
  Queue: {
    bg: "bg-amber-500/10",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-500/20",
  },
  Outreach: {
    bg: "bg-purple-500/10",
    text: "text-purple-600 dark:text-purple-400",
    border: "border-purple-500/20",
  },
  Post: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-500/20",
  },
  Schedule: {
    bg: "bg-violet-500/10",
    text: "text-violet-600 dark:text-violet-400",
    border: "border-violet-500/20",
  },
  Setting: {
    bg: "bg-cyan-500/10",
    text: "text-cyan-600 dark:text-cyan-400",
    border: "border-cyan-500/20",
  },
  Diagnostic: {
    bg: "bg-rose-500/10",
    text: "text-rose-600 dark:text-rose-400",
    border: "border-rose-500/20",
  },
  History: {
    bg: "bg-stone-500/10",
    text: "text-stone-600 dark:text-stone-400",
    border: "border-stone-500/20",
  },
  Action: {
    bg: "bg-primary/10",
    text: "text-primary",
    border: "border-primary/20",
  },
};

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectTab,
  onTogglePause,
  isPaused: propIsPaused,
  onToggleTheme,
  currentTheme = "light",
}) => {
  const {
    pendingItems,
    connectionQueue,
    scheduledPosts,
    commentWindows,
    auditEntries,
    doctorChecks,
    isPaused: contextIsPaused,
    togglePause: contextTogglePause,
    triggerScout,
    runDoctorCheck,
    clearIncident,
    telemetry,
    navigateTo,
    setActivePostForEditing,
    setCurrentTab,
  } = useApp();

  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<FilterCategory>("All");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const effectiveIsPaused = propIsPaused ?? contextIsPaused;
  const effectiveTogglePause = onTogglePause ?? contextTogglePause;

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedCategory("All");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const allDocuments = useMemo(() => {
    return buildSearchIndex({
      pendingItems,
      connectionQueue,
      scheduledPosts,
      commentWindows,
      auditEntries,
      doctorChecks,
      isPaused: effectiveIsPaused,
      onTogglePause: effectiveTogglePause,
      onToggleTheme,
      currentTheme,
      onTriggerScout: triggerScout,
      onRunDoctor: runDoctorCheck,
      onClearIncident: clearIncident,
      hasIncident: Boolean(telemetry?.circuitBreakerTripped),
      onCreateNewPost: () => {
        setActivePostForEditing(null);
        setCurrentTab("composer");
      },
    });
  }, [
    pendingItems,
    connectionQueue,
    scheduledPosts,
    commentWindows,
    auditEntries,
    doctorChecks,
    effectiveIsPaused,
    effectiveTogglePause,
    onToggleTheme,
    currentTheme,
    triggerScout,
    runDoctorCheck,
    clearIncident,
    telemetry,
    setActivePostForEditing,
    setCurrentTab,
  ]);

  const filteredItems = useMemo(() => {
    let pool = allDocuments;
    if (selectedCategory !== "All") {
      pool = pool.filter((doc) => doc.category === selectedCategory);
    }
    return searchAndRank(pool, query, 30);
  }, [allDocuments, selectedCategory, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredItems]);

  const handleSelectItem = (item: SearchDocument) => {
    if (item.action) {
      item.action();
    } else if (item.target) {
      if (onSelectTab) {
        onSelectTab(item.target.tab);
      }
      navigateTo(item.target);
    }
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredItems.length > 0 ? (prev + 1) % filteredItems.length : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredItems.length > 0
          ? (prev - 1 + filteredItems.length) % filteredItems.length
          : 0
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        handleSelectItem(filteredItems[selectedIndex]);
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
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-xs pt-16 px-4 animate-in fade-in duration-100"
    >
      <div
        data-testid="command-palette"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-outline bg-surface-container-low shadow-2xl transition-all flex flex-col max-h-[85vh]"
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-2.5 border-b border-outline px-4 py-3 bg-surface-container-lowest shrink-0">
          <MagnifyingGlass size={16} className="text-on-surface-variant shrink-0" />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search views, pending queue, settings, posts, diagnostics..."
            className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden"
          />
          <kbd className="hidden sm:inline-block rounded-md border border-outline px-1.5 py-0.5 text-[10px] font-mono text-on-surface-variant bg-surface-container-low">
            ESC
          </kbd>
        </div>

        {/* Category Filter Chips */}
        <div className="flex items-center gap-1.5 px-3 py-2 border-b border-outline/50 bg-surface-container-low/80 overflow-x-auto scrollbar-none shrink-0 text-[11px]">
          {CATEGORY_CHIPS.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                type="button"
                data-testid={`filter-chip-${cat.toLowerCase()}`}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-0.5 rounded-full transition-colors font-medium shrink-0 cursor-pointer ${
                  isSelected
                    ? "bg-primary text-on-primary shadow-2xs"
                    : "bg-surface-container text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {cat}
              </button>
            );
          })}
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5 min-h-[140px] max-h-[380px]">
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-xs text-on-surface-variant flex flex-col items-center gap-1">
              <span>No matching items or commands found for &quot;{query}&quot;</span>
              <span className="text-[11px] text-on-surface-variant/70">
                Try searching author names, setting fields, topics, or view tabs
              </span>
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;
              const colorInfo = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.Navigation;

              return (
                <div
                  key={item.id}
                  data-testid={`palette-item-${item.id}`}
                  onClick={() => handleSelectItem(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors text-xs ${
                    isSelected
                      ? "bg-surface-container-highest text-on-surface font-medium"
                      : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                  }`}
                >
                  {/* Category Styled Icon */}
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-md shrink-0 ${
                      isSelected
                        ? "bg-primary text-on-primary"
                        : `${colorInfo.bg} ${colorInfo.text}`
                    }`}
                  >
                    <Icon size={14} weight={isSelected ? "bold" : "regular"} />
                  </div>

                  {/* Title & Subtitle Preview */}
                  <div className="flex flex-col flex-1 overflow-hidden min-w-0">
                    <span className="truncate text-on-surface font-medium">
                      {item.title}
                    </span>
                    <span className="truncate text-[11px] text-on-surface-variant">
                      {item.subtitle}
                    </span>
                  </div>

                  {/* Right Tags / Pills */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {item.badge && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant border border-outline/30">
                        {item.badge}
                      </span>
                    )}
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${colorInfo.bg} ${colorInfo.text} ${colorInfo.border}`}
                    >
                      {item.category}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts hint */}
        <div className="flex items-center justify-between border-t border-outline bg-surface-container-lowest px-4 py-2 text-[10px] text-on-surface-variant shrink-0">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="font-mono font-semibold">↑↓</kbd> navigate
            </span>
            <span>
              <kbd className="font-mono font-semibold">↵</kbd> select &amp; jump
            </span>
            <span>
              <kbd className="font-mono font-semibold">esc</kbd> close
            </span>
          </div>
          <span>{formatKeyCombo("K")} Spotlight</span>
        </div>
      </div>
    </div>
  );
};
