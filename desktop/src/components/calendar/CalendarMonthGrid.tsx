import React, { useMemo } from "react";
import { ScheduledPost } from "../../types";
import { isSameDay } from "./types";

interface CalendarMonthGridProps {
  currentDate: Date;
  filteredPosts: ScheduledPost[];
  onSelectPost: (post: ScheduledPost) => void;
}

const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const CalendarMonthGrid: React.FC<CalendarMonthGridProps> = ({
  currentDate,
  filteredPosts,
  onSelectPost,
}) => {
  const monthDays = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDayOfMonth = new Date(year, month, 1);
    const startDayIndex = (firstDayOfMonth.getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    const cells: {
      date: Date;
      dayNum: number;
      isCurrentMonth: boolean;
      isToday: boolean;
    }[] = [];

    // Leading days from previous month
    for (let i = startDayIndex - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, daysInPrevMonth - i);
      cells.push({
        date: d,
        dayNum: daysInPrevMonth - i,
        isCurrentMonth: false,
        isToday: isSameDay(d, new Date().toISOString()),
      });
    }

    // Days in current month
    for (let day = 1; day <= daysInMonth; day++) {
      const d = new Date(year, month, day);
      cells.push({
        date: d,
        dayNum: day,
        isCurrentMonth: true,
        isToday: isSameDay(d, new Date().toISOString()),
      });
    }

    // Trailing days from next month (35 or 42 cells)
    const totalCells = cells.length > 35 ? 42 : 35;
    const remaining = totalCells - cells.length;
    for (let day = 1; day <= remaining; day++) {
      const d = new Date(year, month + 1, day);
      cells.push({
        date: d,
        dayNum: day,
        isCurrentMonth: false,
        isToday: isSameDay(d, new Date().toISOString()),
      });
    }

    return cells;
  }, [currentDate]);

  return (
    <div
      data-testid="calendar-month-grid"
      className="rounded-2xl border border-surface-container-high/70 bg-surface-container-lowest p-4 shadow-xs"
    >
      {/* Month Days Header */}
      <div className="grid grid-cols-7 gap-2 pb-2.5 border-b border-surface-container-high text-center font-code-sm text-code-sm text-on-surface-variant font-medium">
        {dayNames.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>

      {/* Month Day Cells */}
      <div className="mt-2.5 grid grid-cols-7 gap-2">
        {monthDays.map((cell, i) => {
          const dayPosts = filteredPosts.filter((p) =>
            isSameDay(cell.date, p.scheduled_time)
          );
          const countPosts = dayPosts.length;

          return (
            <div
              key={i}
              className={`min-h-[82px] rounded-xl border p-2 transition-colors flex flex-col justify-between ${
                cell.isToday
                  ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                  : cell.isCurrentMonth
                  ? "border-surface-container-high/70 bg-surface-container-low hover:bg-surface-container"
                  : "border-surface-container-high/40 bg-surface-container-low/30 opacity-40 hover:opacity-75"
              }`}
            >
              <div className="flex items-center justify-between text-[11px]">
                <span
                  className={`font-mono font-medium ${
                    cell.isToday
                      ? "font-bold text-primary"
                      : cell.isCurrentMonth
                      ? "text-on-surface"
                      : "text-on-surface-variant"
                  }`}
                >
                  {cell.dayNum}
                </span>
                {countPosts > 0 && (
                  <span className="rounded-full bg-primary/10 px-1.5 py-0.2 font-code-sm text-[10px] text-primary font-semibold border border-primary/20">
                    {countPosts}
                  </span>
                )}
              </div>

              {countPosts > 0 && (
                <div className="mt-1 flex flex-col gap-1 overflow-hidden">
                  {dayPosts.slice(0, 2).map((p) => (
                    <div
                      key={p.id}
                      onClick={() => onSelectPost(p)}
                      className="cursor-pointer truncate rounded-md bg-surface-container-lowest px-1.5 py-0.5 font-mono text-[9px] text-on-surface hover:text-primary transition-colors border border-surface-container-high shadow-2xs"
                      title={p.headline}
                    >
                      {p.headline || p.id}
                    </div>
                  ))}
                  {countPosts > 2 && (
                    <span className="font-code-sm text-[8px] text-on-surface-variant">
                      +{countPosts - 2} more
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
