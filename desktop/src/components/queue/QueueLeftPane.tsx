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
      <div className="p-4 pb-2.5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="font-headline-md text-on-surface tracking-tight">
              Approval Queue
            </h1>
            <span
              data-testid="pending-count-pill"
              className="inline-flex items-center px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm font-semibold"
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
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface text-on-surface-variant transition-colors disabled:opacity-50"
            >
              <ArrowClockwise
                size={16}
                className={isLoading ? "animate-spin text-primary" : ""}
              />
            </button>
            <button
              type="button"
              data-testid="shortcuts-help-btn"
              onClick={onOpenShortcuts}
              title="Keyboard shortcuts (?)"
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface text-on-surface-variant transition-colors"
            >
              <Keyboard size={16} />
            </button>
          </div>
        </div>

        {/* Minimalist Native Search Input */}
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-outline/50 shadow-xs">
          <MagnifyingGlass size={16} className="text-on-surface-variant shrink-0" />
          <input
            type="text"
            data-testid="queue-search-input"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter pending approvals..."
            className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface placeholder:text-on-surface-variant"
          />
          <span className="font-code-sm text-on-surface-variant px-1 rounded bg-surface-container">
            ⌘K
          </span>
        </div>

        {/* Filter Segmented Tabs */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-surface-container border border-outline/40">
          <button
            type="button"
            onClick={() => onFilterChange("all")}
            className={`flex-1 py-1 px-2 rounded-md font-label-md transition-colors text-center ${
              filterType === "all"
                ? "bg-surface-container-lowest text-on-surface shadow-xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            All ({items.length})
          </button>
          <button
            type="button"
            onClick={() => onFilterChange("comment")}
            className={`flex-1 py-1 px-2 rounded-md font-label-md transition-colors text-center ${
              filterType === "comment"
                ? "bg-surface-container-lowest text-on-surface shadow-xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Comments ({commentCount})
          </button>
          <button
            type="button"
            onClick={() => onFilterChange("post")}
            className={`flex-1 py-1 px-2 rounded-md font-label-md transition-colors text-center ${
              filterType === "post"
                ? "bg-surface-container-lowest text-on-surface shadow-xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Posts ({postCount})
          </button>
        </div>
      </div>

      {/* Quick Triage Keyboard Ribbon */}
      <div className="px-4 py-1.5 flex items-center justify-between text-on-surface-variant bg-surface-container/60 border-y border-outline/40">
        <span className="font-code-sm flex items-center gap-1.5 text-on-surface-variant">
          <span className="px-1 py-0.5 rounded bg-surface-container-highest text-on-surface font-medium">
            J
          </span>
          <span className="px-1 py-0.5 rounded bg-surface-container-highest text-on-surface font-medium">
            K
          </span>
          <span>navigate</span>
          <span className="opacity-40">·</span>
          <span className="px-1 py-0.5 rounded bg-surface-container-highest text-on-surface font-medium">
            A
          </span>
          <span>approve</span>
          <span className="opacity-40">·</span>
          <span className="px-1 py-0.5 rounded bg-surface-container-highest text-on-surface font-medium">
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
        className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-1.5 outline-none"
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
      <div className="p-3 mx-2 mb-2 rounded-lg bg-surface-container-lowest border border-outline/40 flex items-center justify-between text-on-surface-variant shadow-2xs">
        <div className="flex items-center gap-2">
          <Lightning size={15} weight="fill" className="text-tertiary" />
          <span className="font-label-sm">Auto-polling: active</span>
        </div>
        <span className="font-code-sm text-on-surface-variant">Every 5m</span>
      </div>
    </section>
  );
};
