import React, { useState, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { ScheduledPost, ScheduledPostStatus, AutomatedCommentWindow } from "../types";
import {
  Calendar,
  Clock,
  CheckCircle,
  Lightning,
  PencilSimple,
  FilePdf,
  Image as ImageIcon,
  Plus,
  CaretLeft,
  CaretRight,
  X,
} from "../components/icons";

type CalendarViewMode = "week" | "month";
type StatusFilter = "all" | ScheduledPostStatus;

export const CalendarView: React.FC = () => {
  const {
    scheduledPosts,
    commentWindows,
    setCurrentTab,
    setActivePostForEditing,
  } = useApp();

  const [viewMode, setViewMode] = useState<CalendarViewMode>("week");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedPost, setSelectedPost] = useState<ScheduledPost | null>(null);

  // Reference base date anchor (2026-09-29)
  const [currentDate, setCurrentDate] = useState<Date>(() => new Date(2026, 8, 29));

  // Navigate calendar
  const handlePrev = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      if (viewMode === "week") {
        next.setDate(next.getDate() - 7);
      } else {
        next.setMonth(next.getMonth() - 1);
      }
      return next;
    });
  };

  const handleNext = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      if (viewMode === "week") {
        next.setDate(next.getDate() + 7);
      } else {
        next.setMonth(next.getMonth() + 1);
      }
      return next;
    });
  };

  const handleToday = () => {
    setCurrentDate(new Date(2026, 8, 29));
  };

  // Generate 7-day week array starting on Monday of current week
  const weekDays = useMemo(() => {
    const days: Date[] = [];
    const curr = new Date(currentDate);
    const day = curr.getDay(); // 0 is Sun, 1 is Mon
    const diff = curr.getDate() - day + (day === 0 ? -6 : 1); // adjust to Monday
    const monday = new Date(curr.setDate(diff));

    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push(d);
    }
    return days;
  }, [currentDate]);

  // Formatted range label
  const rangeLabel = useMemo(() => {
    if (viewMode === "week") {
      const start = weekDays[0];
      const end = weekDays[6];
      const monthNames = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ];
      return `${monthNames[start.getMonth()]} ${start.getDate()} - ${
        monthNames[end.getMonth()]
      } ${end.getDate()}, ${end.getFullYear()}`;
    } else {
      const monthNames = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
      ];
      return `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    }
  }, [viewMode, weekDays, currentDate]);

  // Filter posts
  const filteredPosts = useMemo(() => {
    if (statusFilter === "all") return scheduledPosts;
    return scheduledPosts.filter((p) => p.status === statusFilter);
  }, [scheduledPosts, statusFilter]);

  // Helper: check if a date string matches day
  const isSameDay = (d1: Date, dateStr?: string | null) => {
    if (!dateStr) return false;
    const d2 = new Date(dateStr);
    if (isNaN(d2.getTime())) return false;
    return (
      d1.getFullYear() === d2.getFullYear() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getDate() === d2.getDate()
    );
  };

  // Status badge styling helper
  const getStatusBadge = (status: ScheduledPostStatus) => {
    switch (status) {
      case "published":
        return (
          <span
            data-testid="status-badge-published"
            className="flex items-center gap-1 rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-300 border border-emerald-500/30"
          >
            <CheckCircle size={10} weight="bold" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span
            data-testid="status-badge-scheduled"
            className="flex items-center gap-1 rounded bg-cyan-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-300 border border-cyan-500/30"
          >
            <Clock size={10} weight="bold" />
            <span>Scheduled</span>
          </span>
        );
      case "draft":
      default:
        return (
          <span
            data-testid="status-badge-draft"
            className="flex items-center gap-1 rounded bg-amber-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-amber-300 border border-amber-500/30"
          >
            <PencilSimple size={10} />
            <span>Draft</span>
          </span>
        );
    }
  };

  // Edit in composer
  const handleEditInComposer = (post: ScheduledPost) => {
    setActivePostForEditing(post);
    setSelectedPost(null);
    setCurrentTab("composer");
  };

  // Days of week labels
  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="space-y-6">
      {/* Calendar Header & View Mode Switcher */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">
              <Calendar size={18} weight="bold" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Content Calendar &amp; Planner
            </h1>
            <span className="rounded border border-zinc-800 bg-zinc-900/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
              HITL Schedule
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Coordinate original thought leadership posts alongside autonomous comment scout engagement windows.
          </p>
        </div>

        {/* Action Controls & New Post */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* View Mode Toggle */}
          <div className="flex rounded-md border border-zinc-800 bg-zinc-900/80 p-0.5 text-xs">
            <button
              type="button"
              data-testid="view-mode-week"
              onClick={() => setViewMode("week")}
              className={`rounded px-3 py-1 font-medium transition-colors ${
                viewMode === "week"
                  ? "bg-zinc-800 text-zinc-100 shadow-xs"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Week View
            </button>
            <button
              type="button"
              data-testid="view-mode-month"
              onClick={() => setViewMode("month")}
              className={`rounded px-3 py-1 font-medium transition-colors ${
                viewMode === "month"
                  ? "bg-zinc-800 text-zinc-100 shadow-xs"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Month View
            </button>
          </div>

          {/* New Post Button */}
          <button
            type="button"
            data-testid="new-post-btn"
            onClick={() => {
              setActivePostForEditing(null);
              setCurrentTab("composer");
            }}
            className="flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-500/50 hover:bg-emerald-500/25 active:translate-y-[1px]"
          >
            <Plus size={14} weight="bold" className="text-emerald-400" />
            <span>New Post</span>
          </button>
        </div>
      </div>

      {/* Date Navigation & Status Filter Strip */}
      <div className="flex flex-col justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 sm:flex-row sm:items-center">
        {/* Navigation Arrows & Range */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            data-testid="cal-prev-btn"
            onClick={handlePrev}
            className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-900/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-100"
            title="Previous interval"
          >
            <CaretLeft size={14} />
          </button>
          <button
            type="button"
            data-testid="cal-today-btn"
            onClick={handleToday}
            className="rounded border border-zinc-800 bg-zinc-900/80 px-2.5 py-1 text-xs font-medium text-zinc-300 hover:border-zinc-700 hover:text-zinc-100"
          >
            Today
          </button>
          <button
            type="button"
            data-testid="cal-next-btn"
            onClick={handleNext}
            className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-900/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-100"
            title="Next interval"
          >
            <CaretRight size={14} />
          </button>

          <span
            data-testid="cal-range-label"
            className="ml-2 font-mono text-xs font-semibold text-zinc-200"
          >
            {rangeLabel}
          </span>
        </div>

        {/* Status Filters */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <button
            type="button"
            data-testid="filter-all"
            onClick={() => setStatusFilter("all")}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              statusFilter === "all"
                ? "bg-zinc-800 text-zinc-100 border border-zinc-700"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            All Items
          </button>
          <button
            type="button"
            data-testid="filter-scheduled"
            onClick={() => setStatusFilter("scheduled")}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              statusFilter === "scheduled"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Scheduled
          </button>
          <button
            type="button"
            data-testid="filter-draft"
            onClick={() => setStatusFilter("draft")}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              statusFilter === "draft"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Drafts
          </button>
          <button
            type="button"
            data-testid="filter-published"
            onClick={() => setStatusFilter("published")}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              statusFilter === "published"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Published
          </button>
        </div>
      </div>

      {/* Week Grid View */}
      {viewMode === "week" && (
        <div
          data-testid="calendar-week-grid"
          className="grid grid-cols-1 gap-3 md:grid-cols-7"
        >
          {weekDays.map((dayDate, idx) => {
            const isToday =
              dayDate.getFullYear() === 2026 &&
              dayDate.getMonth() === 8 &&
              dayDate.getDate() === 29;

            const dayPosts = filteredPosts.filter((p) =>
              isSameDay(dayDate, p.scheduled_time)
            );

            // Automated comment windows applicable to this day (by 3-letter day name)
            const dayCode = dayNames[idx];
            const applicableWindows = commentWindows.filter((w) =>
              w.days.includes(dayCode)
            );

            return (
              <div
                key={dayDate.toISOString()}
                data-testid={`day-col-${dayCode.toLowerCase()}`}
                className={`flex min-h-[360px] flex-col rounded-lg border bg-zinc-900/40 p-2.5 transition-colors ${
                  isToday
                    ? "border-emerald-500/40 bg-zinc-900/80 shadow-xs"
                    : "border-zinc-800/90"
                }`}
              >
                {/* Day Header */}
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-zinc-300">
                      {dayCode}
                    </span>
                    <span className="font-mono text-[11px] text-zinc-500">
                      {dayDate.getDate()}
                    </span>
                  </div>
                  {isToday && (
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" title="Today" />
                  )}
                </div>

                {/* Day Content Area */}
                <div className="mt-2.5 flex-1 space-y-2 overflow-y-auto">
                  {/* Automated Comment Windows */}
                  {applicableWindows.map((win: AutomatedCommentWindow) => (
                    <div
                      key={win.id}
                      data-testid="calendar-comment-window"
                      className="rounded border border-violet-500/30 bg-violet-500/10 p-2 text-left"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1 text-[10px] font-semibold text-violet-300">
                          <Lightning size={11} weight="fill" className="text-violet-400" />
                          <span>Scout Window</span>
                        </div>
                        <span className="font-mono text-[9px] text-violet-400">
                          {win.start_time} - {win.end_time}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-1 text-[10px] text-zinc-300 font-medium">
                        {win.title}
                      </p>
                    </div>
                  ))}

                  {/* Scheduled Original Posts */}
                  {dayPosts.map((post) => {
                    const hasPdf = post.media.some((m) => m.media_type === "carousel_pdf");
                    const hasImg = post.media.some((m) => m.media_type === "image");
                    const timeStr = post.scheduled_time
                      ? new Date(post.scheduled_time)
                          .toISOString()
                          .split("T")[1]
                          ?.substring(0, 5) + " UTC"
                      : "Unscheduled";

                    return (
                      <div
                        key={post.id}
                        data-testid="calendar-post-card"
                        onClick={() => setSelectedPost(post)}
                        className="group cursor-pointer rounded-md border border-zinc-800 bg-zinc-950/80 p-2.5 transition-all duration-150 hover:border-zinc-700 hover:bg-zinc-900 active:translate-y-[1px]"
                      >
                        {/* Status + Time */}
                        <div className="flex items-center justify-between gap-1">
                          {getStatusBadge(post.status)}
                          <span className="font-mono text-[9px] text-zinc-500">
                            {timeStr}
                          </span>
                        </div>

                        {/* Headline */}
                        <h4 className="mt-1.5 line-clamp-2 text-xs font-medium text-zinc-200 group-hover:text-emerald-300">
                          {post.headline || "Untitled Original Post"}
                        </h4>

                        {/* Pillar and Media Badge */}
                        <div className="mt-2 flex items-center justify-between text-[10px] text-zinc-500">
                          <span className="truncate max-w-[90px]">{post.topic_pillar}</span>
                          {hasPdf ? (
                            <span className="flex items-center gap-0.5 text-red-400 font-mono text-[9px]">
                              <FilePdf size={11} />
                              <span>PDF</span>
                            </span>
                          ) : hasImg ? (
                            <span className="flex items-center gap-0.5 text-blue-400 font-mono text-[9px]">
                              <ImageIcon size={11} />
                              <span>IMG</span>
                            </span>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}

                  {/* Empty state when no items on this day */}
                  {dayPosts.length === 0 && applicableWindows.length === 0 && (
                    <div className="flex h-20 items-center justify-center text-center">
                      <span className="text-[11px] text-zinc-700">No events</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Month View Grid */}
      {viewMode === "month" && (
        <div data-testid="calendar-month-grid" className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="grid grid-cols-7 gap-2 pb-2 border-b border-zinc-800 text-center font-mono text-xs text-zinc-500 font-medium">
            {dayNames.map((d) => (
              <div key={d}>{d}</div>
            ))}
          </div>

          <div className="mt-2 grid grid-cols-7 gap-2">
            {/* 35 Month Day Cells Mockup */}
            {Array.from({ length: 35 }).map((_, i) => {
              const dayNum = ((i + 28) % 30) + 1;
              const isToday = i === 1; // Sep 29
              const dayDateStr = `2026-09-${dayNum.toString().padStart(2, "0")}`;
              const countPosts = filteredPosts.filter((p) =>
                p.scheduled_time?.startsWith(dayDateStr)
              ).length;

              return (
                <div
                  key={i}
                  className={`min-h-[72px] rounded-md border p-2 transition-colors ${
                    isToday
                      ? "border-emerald-500/40 bg-zinc-900/90"
                      : "border-zinc-800/80 bg-zinc-950/50 hover:bg-zinc-900/60"
                  }`}
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span
                      className={`font-mono ${
                        isToday ? "font-bold text-emerald-400" : "text-zinc-400"
                      }`}
                    >
                      {dayNum}
                    </span>
                    {countPosts > 0 && (
                      <span className="rounded-full bg-cyan-500/20 px-1.5 py-0.2 font-mono text-[9px] text-cyan-300">
                        {countPosts}
                      </span>
                    )}
                  </div>
                  {countPosts > 0 && (
                    <div className="mt-1 flex flex-col gap-0.5">
                      <div className="h-1 rounded-full bg-cyan-400/80 w-3/4" />
                      <div className="h-1 rounded-full bg-violet-400/60 w-1/2" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bottom Summary Bar: Automated Comment Windows & Status Legend */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Active Comment Windows Strip (7 cols) */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-7">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
            <div className="flex items-center gap-2">
              <Lightning size={16} className="text-violet-400" />
              <h3 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
                Automated High-Signal Comment Windows
              </h3>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">Autonomous Feed Scout</span>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {commentWindows.map((win) => (
              <div
                key={win.id}
                className="flex flex-col justify-between rounded-md border border-zinc-800/90 bg-zinc-950/70 p-3"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-violet-400 font-semibold">
                      {win.start_time} - {win.end_time} UTC
                    </span>
                    <span className="rounded bg-violet-500/10 px-1.5 py-0.2 text-[9px] text-violet-300 font-medium">
                      {win.status}
                    </span>
                  </div>
                  <h4 className="mt-1.5 text-xs font-medium text-zinc-200">
                    {win.title}
                  </h4>
                  <p className="mt-1 line-clamp-1 text-[10px] text-zinc-500">
                    {win.topic_filter}
                  </p>
                </div>
                <div className="mt-2 pt-2 border-t border-zinc-800/60 font-mono text-[9px] text-zinc-600">
                  Runs: {win.days.join(", ")}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Content Strategy Legend & Guidelines (5 cols) */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-5">
          <h3 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
            Schedule Safeguards &amp; Invariants
          </h3>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            Original posts require explicit operator approval before transmission. Rate limits ensure maximum 3 posts and 15 comments per day to protect account health.
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-3 pt-2 border-t border-zinc-800 text-[11px]">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-cyan-400" />
              <span className="text-zinc-300">Scheduled Post</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <span className="text-zinc-300">Draft Post</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-zinc-300">Published</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-violet-400" />
              <span className="text-zinc-300">Comment Window</span>
            </div>
          </div>
        </div>
      </div>

      {/* Post Detail Modal / Inspector */}
      {selectedPost && (
        <div
          data-testid="post-detail-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 p-4 backdrop-blur-xs"
        >
          <div className="relative w-full max-w-xl rounded-lg border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-zinc-800 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(selectedPost.status)}
                  <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
                    {selectedPost.topic_pillar}
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold text-zinc-100">
                  {selectedPost.headline || "Original Scheduled Post"}
                </h3>
              </div>
              <button
                type="button"
                data-testid="close-modal-btn"
                onClick={() => setSelectedPost(null)}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              >
                <X size={16} />
              </button>
            </div>

            {/* Post Content Excerpt */}
            <div className="my-4 max-h-60 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-950 p-4 font-sans text-xs leading-relaxed text-zinc-300 whitespace-pre-wrap">
              {selectedPost.post_text}
            </div>

            {/* Media Information */}
            {selectedPost.media.length > 0 && (
              <div className="mb-4 rounded-md border border-zinc-800 bg-zinc-950/60 p-3">
                <div className="text-[11px] font-semibold text-zinc-400">
                  Attached Media:
                </div>
                {selectedPost.media.map((m, i) => (
                  <div
                    key={i}
                    className="mt-1 flex items-center justify-between font-mono text-xs text-zinc-300"
                  >
                    <div className="flex items-center gap-1.5">
                      {m.media_type === "carousel_pdf" ? (
                        <FilePdf size={14} className="text-red-400" />
                      ) : (
                        <ImageIcon size={14} className="text-blue-400" />
                      )}
                      <span>{m.file_name}</span>
                    </div>
                    <span className="text-[10px] text-zinc-500">
                      {m.media_type === "carousel_pdf"
                        ? `${m.slide_count} slides`
                        : "Image"}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between border-t border-zinc-800 pt-3">
              <span className="font-mono text-[11px] text-zinc-500">
                Scheduled:{" "}
                {selectedPost.scheduled_time
                  ? new Date(selectedPost.scheduled_time).toUTCString()
                  : "Draft"}
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedPost(null)}
                  className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                >
                  Close
                </button>
                <button
                  type="button"
                  data-testid="edit-in-composer-btn"
                  onClick={() => handleEditInComposer(selectedPost)}
                  className="flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/25 active:translate-y-[1px]"
                >
                  <PencilSimple size={13} />
                  <span>Edit in Composer</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
