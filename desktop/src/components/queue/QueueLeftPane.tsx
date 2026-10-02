import React, { RefObject } from "react";
import {
  MagnifyingGlass,
  ArrowClockwise,
  Keyboard,
  Lightning,
} from "@phosphor-icons/react";
import { QueueTriageCard, PendingItem } from "./QueueTriageCard";

export type FilterType = "all" | "comment" | "post";

interface QueueLeftPaneProps {
  items: PendingItem[];
  filteredItems: PendingItem[];
  selectedId: string | null;
  onSelectId: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filterType: FilterType;
  onFilterChange: (filter: FilterType) => void;
  isLoading: boolean;
  onRefresh: () => void;
  onOpenShortcuts: () => void;
  queueListRef: RefObject<HTMLDivElement | null>;
}

export const QueueLeftPane: React.FC<QueueLeftPaneProps> = ({
  items,
  filteredItems,
  selectedId,
  onSelectId,
  searchQuery,
  onSearchChange,
  filterType,
  onFilterChange,
  isLoading,
  onRefresh,
  onOpenShortcuts,
  queueListRef,
}) => {
  const commentCount = items.filter((i) => i.actionType === "comment").length;
  const postCount = items.filter((i) => i.actionType === "post").length;

  return (
    <section className="w-[360px] lg:w-[390px] shrink-0 flex flex-col bg-surface-container-low border-r border-outline select-none h-full">
      {/* Queue Header & Global Controls */}
      <div className="p-3.5 pb-2 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-on-surface tracking-tight">
              Approval Queue
            </h1>
            <span
              data-testid="pending-count-pill"
              className="inline-flex items-center px-1.5 py-0.2 rounded-[4px] bg-surface-container-high text-on-surface text-[10px] font-medium tabular-nums"
            >
              {items.length} Pending
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              data-testid="refresh-queue-btn"
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh queue"
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-container hover:text-on-surface text-on-surface-variant transition-colors disabled:opacity-50"
            >
              <ArrowClockwise
                size={14}
                className={isLoading ? "animate-spin text-primary" : ""}
              />
            </button>
            <button
              type="button"
              data-testid="shortcuts-help-btn"
              onClick={onOpenShortcuts}
              title="Keyboard shortcuts (?)"
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-container hover:text-on-surface text-on-surface-variant transition-colors"
            >
              <Keyboard size={14} />
            </button>
          </div>
        </div>

        {/* Minimalist Native Search Input */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-container-lowest border border-outline/50 shadow-2xs">
          <MagnifyingGlass size={13} className="text-on-surface-variant shrink-0" />
          <input
            type="text"
            data-testid="queue-search-input"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter pending approvals..."
            className="w-full bg-transparent border-0 outline-none text-xs text-on-surface placeholder:text-on-surface-variant"
          />
          <span className="text-[10px] text-on-surface-variant px-1 rounded bg-surface-container font-sans">
            ⌘K
          </span>
        </div>

        {/* Filter Segmented Tabs */}
        <div className="flex items-center gap-0.5 p-0.5 rounded-md bg-surface-container border border-outline/40">
          <button
            type="button"
            onClick={() => onFilterChange("all")}
            className={`flex-1 py-0.5 px-1.5 rounded-sm text-[11px] transition-colors text-center ${
              filterType === "all"
                ? "bg-surface-container-lowest text-on-surface shadow-2xs font-medium"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            All ({items.length})
          </button>
          <button
            type="button"
            onClick={() => onFilterChange("comment")}
            className={`flex-1 py-0.5 px-1.5 rounded-sm text-[11px] transition-colors text-center ${
              filterType === "comment"
                ? "bg-surface-container-lowest text-on-surface shadow-2xs font-medium"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Comments ({commentCount})
          </button>
          <button
            type="button"
            onClick={() => onFilterChange("post")}
            className={`flex-1 py-0.5 px-1.5 rounded-sm text-[11px] transition-colors text-center ${
              filterType === "post"
                ? "bg-surface-container-lowest text-on-surface shadow-2xs font-medium"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Posts ({postCount})
          </button>
        </div>
      </div>

      {/* Quick Triage Keyboard Ribbon */}
      <div className="px-3.5 py-1 flex items-center justify-between text-on-surface-variant bg-surface-container/60 border-y border-outline/40 text-[11px]">
        <span className="flex items-center gap-1.5 text-on-surface-variant">
          <span className="px-1 py-0.2 rounded bg-surface-container-highest text-on-surface font-medium text-[10px]">
            J
          </span>
          <span className="px-1 py-0.2 rounded bg-surface-container-highest text-on-surface font-medium text-[10px]">
            K
          </span>
          <span>navigate</span>
          <span className="opacity-40">·</span>
          <span className="px-1 py-0.2 rounded bg-surface-container-highest text-on-surface font-medium text-[10px]">
            A
          </span>
          <span>approve</span>
          <span className="opacity-40">·</span>
          <span className="px-1 py-0.2 rounded bg-surface-container-highest text-on-surface font-medium text-[10px]">
            R
          </span>
          <span>reject</span>
        </span>
      </div>

      {/* Queue Triage List Items */}
      <div
        ref={queueListRef}
        tabIndex={-1}
        id="triageList"
        className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-1 outline-none"
      >
        {filteredItems.map((item) => (
          <QueueTriageCard
            key={item.id}
            item={item}
            isSelected={item.id === selectedId}
            onSelect={() => onSelectId(item.id)}
          />
        ))}

        {filteredItems.length === 0 && (
          <div className="p-8 text-center text-on-surface-variant text-xs">
            No pending actions match your filter.
          </div>
        )}
      </div>

      {/* Left Pane Sync Status Bar */}
      <div className="p-2.5 mx-2 mb-2 rounded-md bg-surface-container-lowest border border-outline/40 flex items-center justify-between text-on-surface-variant shadow-2xs">
        <div className="flex items-center gap-1.5">
          <Lightning size={14} weight="fill" className="text-tertiary" />
          <span className="text-[11px] font-medium text-on-surface">Auto-polling active</span>
        </div>
        <span className="text-[10px] text-on-surface-variant">Every 5m</span>
      </div>
    </section>
  );
};
