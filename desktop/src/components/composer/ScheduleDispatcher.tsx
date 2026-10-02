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
      className="p-5 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-4"
    >
      <div className="flex items-center justify-between pb-2 border-b border-surface-container-high/60">
        <div className="flex items-center gap-2">
          <Clock size={18} className="text-primary" />
          <span className="font-headline-sm text-headline-sm text-on-surface">
            Schedule Dispatcher
          </span>
        </div>
        <span className="font-label-sm text-label-sm px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-medium">
          Target Slot: 14:00 UTC
        </span>
      </div>

      {/* Date & Time Selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-label-sm text-on-surface-variant font-medium">
            Scheduled Date
          </label>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high/70 focus-within:border-primary/60 transition-colors">
            <Calendar size={15} className="text-on-surface-variant shrink-0" />
            <input
              type="date"
              data-testid="schedule-date-input"
              value={scheduledDate}
              onChange={(e) => setScheduledDate(e.target.value)}
              className="w-full bg-transparent border-0 outline-hidden font-mono text-xs text-on-surface"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-label-sm text-on-surface-variant font-medium">
            Scheduled Time (UTC)
          </label>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high/70 focus-within:border-primary/60 transition-colors">
            <Clock size={15} className="text-on-surface-variant shrink-0" />
            <input
              type="time"
              data-testid="schedule-time-input"
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              className="w-full bg-transparent border-0 outline-hidden font-mono text-xs text-on-surface"
            />
          </div>
        </div>
      </div>

      {/* Edge Guard / Quota Status Pill */}
      <div className="p-3 rounded-xl bg-surface-container flex items-center justify-between text-on-surface-variant text-[12px] border border-surface-container-high/50">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-tertiary" />
          <span className="font-label-sm text-label-sm text-on-surface font-medium">
            Cloudflare Edge Relay Ready
          </span>
        </div>
        <span className="font-code-sm text-code-sm text-on-surface font-semibold">
          11/15 daily cap
        </span>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2.5 pt-1">
        <button
          type="button"
          data-testid="save-draft-btn"
          onClick={onSaveDraft}
          className="py-2.5 px-3 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-strong text-body-strong shadow-2xs transition-colors flex items-center justify-center gap-1.5 border border-surface-container-high"
        >
          <span>Save Draft</span>
        </button>

        <button
          type="button"
          data-testid="schedule-post-btn"
          onClick={onSchedulePost}
          className="py-2.5 px-3 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-body-strong text-body-strong shadow-xs transition-colors flex items-center justify-center gap-1.5"
        >
          <CheckCircle size={15} weight="bold" />
          <span>Schedule Post</span>
        </button>
      </div>
    </div>
  );
};
