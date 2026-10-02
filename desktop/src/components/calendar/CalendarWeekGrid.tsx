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
            className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.2 rounded-[4px] bg-tertiary-container/20 text-on-surface font-medium shrink-0 border border-outline/30"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary shrink-0" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span
            data-testid="status-badge-scheduled"
            className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.2 rounded-[4px] bg-primary/10 text-primary font-medium shrink-0 border border-primary/20"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
            <span>Scheduled</span>
          </span>
        );
      case "draft":
      default:
        return (
          <span
            data-testid="status-badge-draft"
            className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.2 rounded-[4px] bg-surface-container text-on-surface-variant font-medium shrink-0 border border-outline/40"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-outline shrink-0" />
            <span>Draft</span>
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col gap-3.5">
      {/* Empty State Banner (when no posts are scheduled) */}
      {filteredPosts.length === 0 && (
        <div
          data-testid="calendar-empty-prompt"
          className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-md border border-dashed border-outline bg-surface-container-low px-3.5 py-2.5 text-xs text-on-surface-variant"
        >
          <div className="flex items-center gap-2">
            <Calendar size={15} className="text-on-surface-variant shrink-0" />
            <span>
              No scheduled posts found for this view. Create a new post in Composer to schedule content.
            </span>
          </div>
          <button
            type="button"
            data-testid="empty-new-post-btn"
            onClick={onNewPost}
            className="shrink-0 flex items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary/20 transition-colors"
          >
            <Plus size={13} weight="bold" />
            <span>New Post</span>
          </button>
        </div>
      )}

      {/* 7-Day Weekly Grid (Crisp Apple Calendar aesthetic) */}
      <div
        data-testid="calendar-week-grid"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-2.5"
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
              className={`flex flex-col gap-2 rounded-lg p-2.5 min-h-[440px] transition-colors border ${
                isToday
                  ? "bg-surface-container-lowest shadow-2xs ring-1 ring-primary/20 border-primary/40 relative"
                  : "bg-surface-container-low/60 border-outline/50"
              }`}
            >
              {/* Day Header */}
              <div className="flex items-center justify-between px-1 py-0.5">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`font-mono text-[11px] uppercase tracking-wider font-semibold ${
                      isToday ? "text-primary" : "text-on-surface-variant"
                    }`}
                  >
                    {dayCode}
                  </span>
                  {isToday && (
                    <span className="px-1 py-0.2 rounded-[3px] bg-primary/15 text-primary text-[9px] font-semibold border border-primary/20">
                      TODAY
                    </span>
                  )}
                </div>

                {isToday ? (
                  <div className="w-5 h-5 rounded-full bg-primary text-on-primary flex items-center justify-center text-xs font-semibold">
                    {dayDate.getDate()}
                  </div>
                ) : (
                  <span className="text-xs text-on-surface font-medium">
                    {dayDate.getDate()}
                  </span>
                )}
              </div>

              {/* Day Content Area */}
              <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto">
                {/* Automated Comment Windows */}
                {applicableWindows.map((win) => (
                  <div
                    key={win.id}
                    data-testid="calendar-comment-window"
                    className={`p-2 rounded-md border shadow-2xs flex flex-col gap-0.5 transition-colors cursor-pointer ${
                      isToday
                        ? "bg-primary-container/10 border-primary/30 hover:bg-primary-container/20"
                        : "bg-surface-container-lowest border-outline/50 hover:border-outline"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`font-mono text-[10px] font-semibold tabular-nums ${
                          isToday ? "text-primary" : "text-secondary"
                        }`}
                      >
                        {win.start_time} - {win.end_time} UTC
                      </span>
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isToday ? "bg-primary" : "bg-secondary"
                        }`}
                      />
                    </div>
                    <span className="text-xs font-medium text-on-surface truncate">
                      {win.title}
                    </span>
                    <span className="text-[10px] text-on-surface-variant truncate">
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
                      className="p-2 rounded-md bg-surface-container-lowest shadow-2xs border border-outline/50 hover:border-outline transition-colors flex flex-col gap-1 cursor-pointer min-w-0"
                    >
                      <div className="flex items-center justify-between gap-1 w-full min-w-0 flex-wrap">
                        <span
                          className={`font-mono text-[10px] font-semibold shrink-0 tabular-nums ${
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

                      <h2 className="text-xs font-semibold text-on-surface line-clamp-2 min-w-0 hover:text-primary transition-colors">
                        {post.headline || "Untitled Original Post"}
                      </h2>

                      <div className="flex items-center justify-between pt-1 border-t border-outline/40 min-w-0">
                        <span className="text-[10px] text-on-surface-variant truncate">
                          {post.topic_pillar}
                        </span>
                        {hasPdf ? (
                          <span
                            className="flex items-center gap-0.5 text-error font-mono text-[9px]"
                            title="Carousel PDF Document"
                          >
                            <FilePdf size={12} weight="bold" />
                          </span>
                        ) : hasImg ? (
                          <span
                            className="flex items-center gap-0.5 text-primary font-mono text-[9px]"
                            title="Image Attachment"
                          >
                            <ImageIcon size={12} />
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}

                {/* Empty State when no events on this day */}
                {dayPosts.length === 0 && applicableWindows.length === 0 && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-3">
                    <span className="text-[11px] text-on-surface-variant/70">
                      No events
                    </span>
                    <span className="font-mono text-[10px] text-outline/60 mt-0.5">
                      No events scheduled
                    </span>
                  </div>
                )}

                {/* Live Operator Session indicator for Today */}
                {isToday && (
                  <div className="mt-auto p-1.5 rounded-md bg-surface-container-low text-center border border-outline/50">
                    <span className="text-[11px] text-primary font-medium flex items-center justify-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
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
