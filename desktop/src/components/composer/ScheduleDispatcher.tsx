import React from "react";
import { Calendar, Clock, CheckCircle, ShieldCheck } from "../icons";

interface ScheduleDispatcherProps {
  scheduledDate: string;
  setScheduledDate: (date: string) => void;
  scheduledTime: string;
  setScheduledTime: (time: string) => void;
  onSaveDraft: () => void;
  onSchedulePost: () => void;
}

export const ScheduleDispatcher: React.FC<ScheduleDispatcherProps> = ({
  scheduledDate,
  setScheduledDate,
  scheduledTime,
  setScheduledTime,
  onSaveDraft,
  onSchedulePost,
}) => {
  return (
    <div
      data-testid="scheduling-bar"
      className="p-4 rounded-lg bg-surface-container-lowest border border-outline/70 shadow-2xs flex flex-col gap-3.5"
    >
      <div className="flex items-center justify-between pb-2 border-b border-outline/50">
        <div className="flex items-center gap-2">
          <Clock size={16} className="text-primary" />
          <span className="text-xs font-semibold text-on-surface">
            Schedule Dispatcher
          </span>
        </div>
        <span className="text-[11px] text-primary font-medium">
          Target Slot: 14:00 UTC
        </span>
      </div>

      {/* Date & Time Selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-on-surface-variant font-medium">
            Scheduled Date
          </label>
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-surface-container-low border border-outline/60 focus-within:border-primary/60 transition-colors">
            <Calendar size={14} className="text-on-surface-variant shrink-0" />
            <input
              type="date"
              data-testid="schedule-date-input"
              value={scheduledDate}
              onChange={(e) => setScheduledDate(e.target.value)}
              className="w-full bg-transparent border-0 outline-none font-mono text-xs text-on-surface cursor-pointer"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-on-surface-variant font-medium">
            Scheduled Time (UTC)
          </label>
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-surface-container-low border border-outline/60 focus-within:border-primary/60 transition-colors">
            <Clock size={14} className="text-on-surface-variant shrink-0" />
            <input
              type="time"
              data-testid="schedule-time-input"
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              className="w-full bg-transparent border-0 outline-none font-mono text-xs text-on-surface cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* Edge Guard / Quota Status Pill */}
      <div className="p-2.5 rounded-md bg-surface-container/70 flex items-center justify-between text-on-surface-variant text-[11px] border border-outline/40">
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={14} className="text-tertiary" />
          <span className="text-on-surface font-medium">
            Cloudflare Edge Relay
          </span>
        </div>
        <span className="font-mono text-[11px] text-on-surface font-medium tabular-nums">
          11/15 daily cap
        </span>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2 pt-0.5">
        <button
          type="button"
          data-testid="save-draft-btn"
          onClick={onSaveDraft}
          className="py-1.5 px-3 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-medium shadow-2xs transition-colors flex items-center justify-center gap-1.5 border border-outline/60"
        >
          <span>Save Draft</span>
        </button>

        <button
          type="button"
          data-testid="schedule-post-btn"
          onClick={onSchedulePost}
          className="py-1.5 px-3 rounded-md bg-primary hover:bg-primary/90 text-on-primary text-xs font-semibold shadow-2xs transition-colors flex items-center justify-center gap-1.5"
        >
          <CheckCircle size={14} weight="bold" />
          <span>Schedule Post</span>
        </button>
      </div>
    </div>
  );
};
