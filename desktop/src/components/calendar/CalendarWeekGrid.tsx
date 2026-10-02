import React from "react";
import { ScheduledPost, ScheduledPostStatus, AutomatedCommentWindow } from "../../types";
import {
  Calendar,
  FilePdf,
  Image as ImageIcon,
  Plus,
} from "../icons";
import { isSameDay } from "./types";

interface CalendarWeekGridProps {
  weekDays: Date[];
  filteredPosts: ScheduledPost[];
  commentWindows: AutomatedCommentWindow[];
  onSelectPost: (post: ScheduledPost) => void;
  onNewPost: () => void;
}

const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const CalendarWeekGrid: React.FC<CalendarWeekGridProps> = ({
  weekDays,
  filteredPosts,
  commentWindows,
  onSelectPost,
  onNewPost,
}) => {
  // Status badge styling helper
  const getStatusBadge = (status: ScheduledPostStatus) => {
    switch (status) {
      case "published":
        return (
          <span
            data-testid="status-badge-published"
            className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed font-semibold shrink-0"
          >
            <span className="w-1 h-1 rounded-full bg-tertiary shrink-0" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span
            data-testid="status-badge-scheduled"
            className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-semibold shrink-0"
          >
            <span className="w-1 h-1 rounded-full bg-primary shrink-0" />
            <span>Scheduled</span>
          </span>
        );
      case "draft":
      default:
        return (
          <span
            data-testid="status-badge-draft"
            className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-medium shrink-0"
          >
            <span className="w-1 h-1 rounded-full bg-outline shrink-0" />
            <span>Draft</span>
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Empty State Banner (when no posts are scheduled) */}
      {filteredPosts.length === 0 && (
        <div
          data-testid="calendar-empty-prompt"
          className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-xl border border-dashed border-outline-variant bg-surface-container-low px-4 py-3 text-xs text-on-surface-variant"
        >
          <div className="flex items-center gap-2">
            <Calendar size={16} className="text-on-surface-variant shrink-0" />
            <span>
              No scheduled posts found for this view. Create a new post in Composer to schedule content.
            </span>
          </div>
          <button
            type="button"
            data-testid="empty-new-post-btn"
            onClick={onNewPost}
            className="shrink-0 flex items-center gap-1 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1 font-semibold text-primary hover:bg-primary/20 transition-colors"
          >
            <Plus size={13} weight="bold" />
            <span>New Post</span>
          </button>
        </div>
      )}

      {/* 7-Day Weekly Grid (Crisp Apple Calendar / Things 3 aesthetic) */}
      <div
        data-testid="calendar-week-grid"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-3"
      >
        {weekDays.map((dayDate, idx) => {
          const isToday = isSameDay(dayDate, new Date().toISOString());
          const dayCode = dayNames[idx];

          const dayPosts = filteredPosts.filter((p) =>
            isSameDay(dayDate, p.scheduled_time)
          );

          // Automated comment windows applicable to this day (by 3-letter day name)
          const applicableWindows = commentWindows.filter((w) =>
            w.days.includes(dayCode)
          );

          return (
            <div
              key={dayDate.toISOString()}
              data-testid={`day-col-${dayCode.toLowerCase()}`}
              className={`flex flex-col gap-2.5 rounded-xl p-3 min-h-[460px] transition-all border ${
                isToday
                  ? "bg-surface-container-lowest shadow-sm ring-1 ring-primary/30 border-primary/30 relative"
                  : "bg-surface-container-low/60 border-surface-container-high/60"
              }`}
            >
              {/* Day Header */}
              <div className="flex items-center justify-between px-1 py-0.5">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`font-label-sm text-label-sm uppercase tracking-wider font-semibold ${
                      isToday ? "text-primary" : "text-on-surface-variant"
                    }`}
                  >
                    {dayCode}
                  </span>
                  {isToday && (
                    <span className="px-1.5 py-0.2 rounded bg-primary-fixed text-on-primary-fixed font-label-sm text-[10px] font-semibold">
                      TODAY
                    </span>
                  )}
                </div>

                {isToday ? (
                  <div className="w-6 h-6 rounded-full bg-primary text-on-primary flex items-center justify-center font-label-md text-label-md font-semibold">
                    {dayDate.getDate()}
                  </div>
                ) : (
                  <span className="font-headline-sm text-headline-sm text-on-surface font-medium">
                    {dayDate.getDate()}
                  </span>
                )}
              </div>

              {/* Day Content Area */}
              <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
                {/* Automated Comment Windows */}
                {applicableWindows.map((win) => (
                  <div
                    key={win.id}
                    data-testid="calendar-comment-window"
                    className={`p-2.5 rounded-lg border shadow-2xs flex flex-col gap-1 transition-colors cursor-pointer ${
                      isToday
                        ? "bg-primary-fixed/20 border-primary-fixed-dim/40 hover:bg-primary-fixed/30"
                        : "bg-surface-container-lowest border-surface-container-high/70 hover:border-secondary/40"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`font-code-sm text-code-sm font-semibold ${
                          isToday ? "text-primary" : "text-secondary"
                        }`}
                      >
                        {win.start_time} - {win.end_time} UTC
                      </span>
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isToday ? "bg-primary animate-pulse" : "bg-secondary"
                        }`}
                      />
                    </div>
                    <span className="font-body-strong text-body-strong text-on-surface truncate">
                      {win.title}
                    </span>
                    <span className="font-label-sm text-label-sm text-on-surface-variant truncate">
                      {win.topic_filter}
                    </span>
                  </div>
                ))}

                {/* Scheduled / Draft / Published Original Posts */}
                {dayPosts.map((post) => {
                  const hasPdf = post.media.some((m) => m.media_type === "carousel_pdf");
                  const hasImg = post.media.some((m) => m.media_type === "image");
                  const timeStr = post.scheduled_time
                    ? new Date(post.scheduled_time)
                        .toISOString()
                        .split("T")[1]
                        ?.substring(0, 5) + " UTC"
                    : "Draft";

                  return (
                    <div
                      key={post.id}
                      data-testid="calendar-post-card"
                      onClick={() => onSelectPost(post)}
                      className="p-2.5 rounded-xl bg-surface-container-lowest shadow-2xs border border-surface-container-high hover:shadow-md hover:border-primary/40 transition-all flex flex-col gap-1.5 cursor-pointer min-w-0"
                    >
                      <div className="flex items-center justify-between gap-1 w-full min-w-0 flex-wrap">
                        <span
                          className={`font-code-sm text-[10px] font-semibold shrink-0 ${
                            post.status === "published"
                              ? "text-tertiary"
                              : post.status === "scheduled"
                              ? "text-primary"
                              : "text-on-surface-variant"
                          }`}
                        >
                          {timeStr}
                        </span>
                        {getStatusBadge(post.status)}
                      </div>

                      <h2 className="font-body-strong text-body-strong text-on-surface line-clamp-2 min-w-0 hover:text-primary transition-colors">
                        {post.headline || "Untitled Original Post"}
                      </h2>

                      <div className="flex items-center justify-between pt-1 border-t border-surface-container min-w-0">
                        <span className="font-label-sm text-label-sm text-on-surface-variant truncate">
                          {post.topic_pillar}
                        </span>
                        {hasPdf ? (
                          <span
                            className="flex items-center gap-0.5 text-error font-mono text-[9px]"
                            title="Carousel PDF Document"
                          >
                            <FilePdf size={13} weight="bold" />
                          </span>
                        ) : hasImg ? (
                          <span
                            className="flex items-center gap-0.5 text-primary font-mono text-[9px]"
                            title="Image Attachment"
                          >
                            <ImageIcon size={13} />
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}

                {/* Empty State when no events on this day */}
                {dayPosts.length === 0 && applicableWindows.length === 0 && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-3">
                    <span className="font-label-md text-label-md text-on-surface-variant/70">
                      No events
                    </span>
                    <span className="font-code-sm text-[10px] text-outline/60 mt-1">
                      Autonomous quiet mode
                    </span>
                  </div>
                )}

                {/* Live Operator Session indicator for Today */}
                {isToday && (
                  <div className="mt-auto p-2 rounded-lg bg-surface-container-low text-center border border-surface-container-high/60">
                    <span className="font-label-sm text-label-sm text-primary font-medium flex items-center justify-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                      Live Operator Session
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
