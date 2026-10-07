import React, { useState, useEffect } from "react";
import { AutomatedCommentWindow } from "../../types";
import {
  X,
  Plus,
  Trash,
  Clock,
  Lightning,
  CheckCircle,
  WarningCircle,
} from "../icons";
import {
  convertUtcTimeToLocal,
  convertLocalTimeToUtc,
  getTimezoneOffsetString,
} from "../../utils/datetime";

interface ScoutScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  commentWindows: AutomatedCommentWindow[];
  onSave: (updated: AutomatedCommentWindow[]) => Promise<boolean>;
  timezone: string;
}

interface EditableWindow {
  id: string;
  title: string;
  local_start_time: string;
  local_end_time: string;
  days: string[];
  status: "active" | "standby" | "paused";
  topic_filter: string;
}

const ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];

export const ScoutScheduleModal: React.FC<ScoutScheduleModalProps> = ({
  isOpen,
  onClose,
  commentWindows,
  onSave,
  timezone,
}) => {
  const [windows, setWindows] = useState<EditableWindow[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize editable windows from prop on open
  useEffect(() => {
    if (!isOpen) return;

    const initial: EditableWindow[] = (commentWindows || []).map((w, idx) => {
      const localStart =
        w.local_start_time || convertUtcTimeToLocal(w.start_time, timezone);
      const localEnd =
        w.local_end_time || convertUtcTimeToLocal(w.end_time, timezone);

      return {
        id: w.id || `scout-win-${idx + 1}`,
        title: w.title || `Feed Scout Window ${idx + 1}`,
        local_start_time: localStart || "08:00",
        local_end_time: localEnd || "09:30",
        days: Array.isArray(w.days) && w.days.length > 0 ? [...w.days] : [...WEEKDAYS],
        status: w.status || "active",
        topic_filter: w.topic_filter || "",
      };
    });

    setWindows(initial);
    setError(null);
  }, [isOpen, commentWindows, timezone]);

  if (!isOpen) return null;

  const handleUpdate = <K extends keyof EditableWindow>(
    idx: number,
    field: K,
    val: EditableWindow[K]
  ) => {
    setWindows((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: val };
      return next;
    });
  };

  const handleToggleDay = (idx: number, day: string) => {
    setWindows((prev) => {
      const next = [...prev];
      const currentDays = next[idx].days;
      if (currentDays.includes(day)) {
        if (currentDays.length <= 1) return prev; // Keep at least 1 day
        next[idx] = { ...next[idx], days: currentDays.filter((d) => d !== day) };
      } else {
        next[idx] = { ...next[idx], days: [...currentDays, day] };
      }
      return next;
    });
  };

  const handleSetPresetDays = (idx: number, preset: "weekdays" | "all") => {
    setWindows((prev) => {
      const next = [...prev];
      next[idx] = {
        ...next[idx],
        days: preset === "weekdays" ? [...WEEKDAYS] : [...ALL_DAYS],
      };
      return next;
    });
  };

  const handleAddWindow = () => {
    const nextIdx = windows.length + 1;
    const newWin: EditableWindow = {
      id: `scout-win-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      title: `Scout Window ${nextIdx}`,
      local_start_time: "15:00",
      local_end_time: "16:30",
      days: [...WEEKDAYS],
      status: "active",
      topic_filter: "Technical Architecture & Systems",
    };
    setWindows((prev) => [...prev, newWin]);
  };

  const handleRemoveWindow = (idx: number) => {
    if (windows.length <= 1) {
      setError("At least one scout window must remain configured.");
      return;
    }
    setWindows((prev) => prev.filter((_, i) => i !== idx));
    setError(null);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e && typeof e.preventDefault === "function") {
      e.preventDefault();
    }
    if (windows.length === 0) {
      setError("Please configure at least one scout window.");
      return;
    }

    // Convert local times to UTC and construct full AutomatedCommentWindow items
    const payload: AutomatedCommentWindow[] = windows.map((w) => {
      const utcStart = convertLocalTimeToUtc(w.local_start_time, timezone);
      const utcEnd = convertLocalTimeToUtc(w.local_end_time, timezone);

      return {
        id: w.id,
        title: w.title.trim() || "Automated Scout Window",
        start_time: utcStart,
        end_time: utcEnd,
        days: w.days,
        status: w.status,
        topic_filter: w.topic_filter.trim(),
        local_start_time: w.local_start_time,
        local_end_time: w.local_end_time,
        timezone,
      };
    });

    setIsSaving(true);
    setError(null);
    try {
      const ok = await onSave(payload);
      if (ok) {
        onClose();
      } else {
        setError("Failed to persist scout schedule to Cloudflare Worker.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error saving scout schedule");
    } finally {
      setIsSaving(false);
    }
  };

  const tzOffset = getTimezoneOffsetString(timezone);
  const activeCount = windows.filter((w) => w.status === "active").length;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-surface-container-lowest rounded-xl border border-outline shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-outline/50 bg-surface-container-low/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center text-primary">
              <Lightning size={18} weight="fill" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-on-surface">
                Configure Automated Scout Runs
              </h2>
              <p className="text-[11px] text-on-surface-variant">
                Adjust the number of daily runs, time windows, and active days
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Form */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
          {/* Info bar */}
          <div className="flex items-center justify-between px-5 py-2.5 bg-surface-container-low/80 border-b border-outline/40 text-[11px] text-on-surface-variant">
            <div className="flex items-center gap-1.5">
              <Clock size={14} className="text-primary" />
              <span>
                Times formatted in your timezone:{" "}
                <span className="font-semibold text-on-surface font-mono">
                  {timezone} ({tzOffset})
                </span>
              </span>
            </div>
            <div className="font-medium text-primary">
              {activeCount} of {windows.length} run{windows.length !== 1 ? "s" : ""} active
            </div>
          </div>

          {/* Windows List */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {error && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-error/10 border border-error/30 text-error">
                <WarningCircle size={16} weight="fill" className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {windows.map((win, idx) => (
              <div
                key={win.id}
                className={`p-3.5 rounded-lg border transition-colors flex flex-col gap-3 ${
                  win.status === "active"
                    ? "bg-surface-container-low border-outline/70 shadow-2xs"
                    : "bg-surface-container-lowest/60 border-outline/40 opacity-75"
                }`}
              >
                {/* Row 1: Title, Status, and Delete */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="w-5 h-5 rounded-full bg-surface-container-highest text-[10px] font-mono font-semibold flex items-center justify-center text-on-surface-variant shrink-0">
                      {idx + 1}
                    </span>
                    <input
                      type="text"
                      value={win.title}
                      onChange={(e) => handleUpdate(idx, "title", e.target.value)}
                      placeholder="Window Title (e.g. Morning Feed Scout)"
                      className="w-full bg-surface-container-lowest px-2.5 py-1 rounded text-xs text-on-surface border border-outline/50 focus:border-primary focus:outline-hidden"
                    />
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Toggle Active Status */}
                    <button
                      type="button"
                      onClick={() =>
                        handleUpdate(
                          idx,
                          "status",
                          win.status === "active" ? "paused" : "active"
                        )
                      }
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors border ${
                        win.status === "active"
                          ? "bg-primary/10 text-primary border-primary/30"
                          : "bg-surface-container-highest text-on-surface-variant border-outline/50"
                      }`}
                    >
                      {win.status === "active" ? "Active" : "Paused"}
                    </button>

                    {/* Delete Window */}
                    <button
                      type="button"
                      onClick={() => handleRemoveWindow(idx)}
                      disabled={windows.length <= 1}
                      title="Remove this scout window"
                      className="p-1 rounded text-on-surface-variant hover:text-error hover:bg-error/10 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      <Trash size={14} />
                    </button>
                  </div>
                </div>

                {/* Row 2: Time Pickers & Topic Filter */}
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5">
                  <div className="sm:col-span-3 flex flex-col gap-1">
                    <label className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">
                      Start Time
                    </label>
                    <input
                      type="time"
                      value={win.local_start_time}
                      onChange={(e) =>
                        handleUpdate(idx, "local_start_time", e.target.value)
                      }
                      className="w-full bg-surface-container-lowest px-2 py-1 rounded text-xs font-mono text-on-surface border border-outline/50 focus:border-primary focus:outline-hidden tabular-nums"
                    />
                  </div>

                  <div className="sm:col-span-3 flex flex-col gap-1">
                    <label className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">
                      End Time
                    </label>
                    <input
                      type="time"
                      value={win.local_end_time}
                      onChange={(e) =>
                        handleUpdate(idx, "local_end_time", e.target.value)
                      }
                      className="w-full bg-surface-container-lowest px-2 py-1 rounded text-xs font-mono text-on-surface border border-outline/50 focus:border-primary focus:outline-hidden tabular-nums"
                    />
                  </div>

                  <div className="sm:col-span-6 flex flex-col gap-1">
                    <label className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">
                      Topic Focus / Filter
                    </label>
                    <input
                      type="text"
                      value={win.topic_filter}
                      onChange={(e) =>
                        handleUpdate(idx, "topic_filter", e.target.value)
                      }
                      placeholder="Engineering Leadership & AI Systems"
                      className="w-full bg-surface-container-lowest px-2.5 py-1 rounded text-xs text-on-surface border border-outline/50 focus:border-primary focus:outline-hidden"
                    />
                  </div>
                </div>

                {/* Row 3: Active Days Chips */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-outline/30">
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] text-on-surface-variant mr-1">
                      Days:
                    </span>
                    {ALL_DAYS.map((day) => {
                      const isSelected = win.days.includes(day);
                      return (
                        <button
                          key={day}
                          type="button"
                          onClick={() => handleToggleDay(idx, day)}
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium transition-colors ${
                            isSelected
                              ? "bg-primary text-on-primary shadow-2xs"
                              : "bg-surface-container-highest text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                          }`}
                        >
                          {day}
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-1.5 text-[10px]">
                    <button
                      type="button"
                      onClick={() => handleSetPresetDays(idx, "weekdays")}
                      className="text-on-surface-variant hover:text-primary transition-colors underline decoration-dotted"
                    >
                      Mon–Fri
                    </button>
                    <span className="text-outline">|</span>
                    <button
                      type="button"
                      onClick={() => handleSetPresetDays(idx, "all")}
                      className="text-on-surface-variant hover:text-primary transition-colors underline decoration-dotted"
                    >
                      All Days
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* Add Window Button */}
            <button
              type="button"
              onClick={handleAddWindow}
              className="w-full py-2.5 rounded-lg border border-dashed border-outline/70 hover:border-primary text-on-surface-variant hover:text-primary text-xs font-medium flex items-center justify-center gap-2 transition-colors bg-surface-container-low/40 hover:bg-surface-container-low cursor-pointer"
            >
              <Plus size={14} weight="bold" />
              <span>Add Another Scout Window</span>
            </button>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-5 py-3 border-t border-outline/50 bg-surface-container-low/50">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-3.5 py-1.5 rounded-md text-xs font-medium text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
            >
              Cancel
            </button>

            <button
              type="submit"
              onClick={(e) => {
                e.preventDefault();
                void handleSubmit(e);
              }}
              disabled={isSaving}
              className="px-4 py-1.5 rounded-md text-xs font-medium bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-1.5 shadow-2xs"
            >
              {isSaving ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Saving to Worker...</span>
                </>
              ) : (
                <>
                  <CheckCircle size={14} weight="bold" />
                  <span>Save &amp; Sync Schedule</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
