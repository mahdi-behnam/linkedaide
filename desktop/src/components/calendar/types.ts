import { ScheduledPost, ScheduledPostStatus, AutomatedCommentWindow } from "../../types";

export type CalendarViewMode = "week" | "month";
export type StatusFilter = "all" | ScheduledPostStatus | "scout";

export interface CalendarViewProps {
  initialPosts?: ScheduledPost[];
  initialCommentWindows?: AutomatedCommentWindow[];
}

export const isSameDay = (d1: Date, dateStr?: string | null): boolean => {
  if (!dateStr) return false;
  const d2 = new Date(dateStr);
  if (isNaN(d2.getTime())) return false;
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
};
