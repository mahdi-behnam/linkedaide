import React from "react";
import {
  CaretLeft,
  CaretRight,
  Plus,
} from "../icons";
import { CalendarViewMode, StatusFilter } from "./types";

interface CalendarHeaderProps {
  viewMode: CalendarViewMode;
  setViewMode: (mode: CalendarViewMode) => void;
  statusFilter: StatusFilter;
  setStatusFilter: (filter: StatusFilter) => void;
  rangeLabel: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onNewPost: () => void;
}

export const CalendarHeader: React.FC<CalendarHeaderProps> = ({
  viewMode,
  setViewMode,
  statusFilter,
  setStatusFilter,
  rangeLabel,
  onPrev,
  onNext,
  onToday,
  onNewPost,
}) => {
  return (
    <div className="flex flex-col gap-4 pb-2 border-b border-surface-container-high/70">
      {/* Top row: Title, Subtitle, View Switcher & New Post */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight font-semibold">
              Content Calendar &amp; Planner
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-sm text-label-sm font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
              HITL Schedule
            </span>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Coordinate original thought leadership posts alongside autonomous comment scout engagement windows.
          </p>
        </div>

        {/* View mode segmented switcher & New Post */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Things 3 segmented control */}
          <div className="flex items-center p-0.5 rounded-lg bg-surface-container border border-surface-container-high/60">
            <button
              type="button"
              data-testid="view-mode-week"
              onClick={() => setViewMode("week")}
              className={`px-3 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
                viewMode === "week"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              Week View
            </button>
            <button
              type="button"
              data-testid="view-mode-month"
              onClick={() => setViewMode("month")}
              className={`px-3 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
                viewMode === "month"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              Month View
            </button>
          </div>

          {/* New Post Button */}
          <button
            type="button"
            data-testid="new-post-btn"
            onClick={onNewPost}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-body-strong text-body-strong shadow-xs transition-colors whitespace-nowrap flex-shrink-0"
          >
            <Plus size={15} weight="bold" />
            <span>New Post</span>
          </button>
        </div>
      </div>

      {/* Date Navigation Stepper & Status Filter Tabs Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Stepper Navigator */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center bg-surface-container rounded-lg p-0.5 shadow-2xs border border-surface-container-high/60">
            <button
              type="button"
              data-testid="cal-prev-btn"
              onClick={onPrev}
              title="Previous interval"
              className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-container-lowest text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <CaretLeft size={14} />
            </button>
            <button
              type="button"
              data-testid="cal-today-btn"
              onClick={onToday}
              className="px-2.5 h-7 rounded-md font-label-md text-label-md text-on-surface hover:bg-surface-container-lowest transition-colors font-medium whitespace-nowrap"
            >
              Today
            </button>
            <button
              type="button"
              data-testid="cal-next-btn"
              onClick={onNext}
              title="Next interval"
              className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-container-lowest text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <CaretRight size={14} />
            </button>
          </div>

          <span
            data-testid="cal-range-label"
            className="font-headline-sm text-headline-sm text-on-surface px-1 font-semibold"
          >
            {rangeLabel}
          </span>
        </div>

        {/* Status Filters */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-surface-container border border-surface-container-high/60 overflow-x-auto">
          <button
            type="button"
            data-testid="filter-all"
            onClick={() => setStatusFilter("all")}
            className={`px-2.5 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
              statusFilter === "all"
                ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            All Items
          </button>
          <button
            type="button"
            data-testid="filter-scheduled"
            onClick={() => setStatusFilter("scheduled")}
            className={`px-2.5 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
              statusFilter === "scheduled"
                ? "bg-surface-container-lowest text-primary shadow-2xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Scheduled
          </button>
          <button
            type="button"
            data-testid="filter-draft"
            onClick={() => setStatusFilter("draft")}
            className={`px-2.5 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
              statusFilter === "draft"
                ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Drafts
          </button>
          <button
            type="button"
            data-testid="filter-published"
            onClick={() => setStatusFilter("published")}
            className={`px-2.5 py-1 rounded-md font-label-md text-label-md transition-colors whitespace-nowrap flex-shrink-0 ${
              statusFilter === "published"
                ? "bg-surface-container-lowest text-tertiary shadow-2xs font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Published
          </button>
        </div>
      </div>
    </div>
  );
};
