import { ScheduledPost, ScheduledPostStatus, AutomatedCommentWindow } from "../../types";

export type CalendarViewMode = "week" | "month";
export type StatusFilter = "all" | ScheduledPostStatus | "scout";

export interface CalendarViewProps {
  initialPosts?: ScheduledPost[];
  initialCommentWindows?: AutomatedCommentWindow[];
}

export const isSameDay = (d1: Date, dateStr?: string | null, timezone?: string): boolean => {
  if (!dateStr) return false;
  const d2 = new Date(dateStr);
  if (isNaN(d2.getTime())) return false;
  if (timezone) {
    try {
      const fmt = new Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
      return fmt.format(d1) === fmt.format(d2);
    } catch {
      // fallback to standard comparison
    }
  }
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
};
