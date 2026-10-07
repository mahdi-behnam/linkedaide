import React, { useState } from "react";
import { useApp } from "../../context/AppContext";
import {
  Lightning,
  Clock,
  Plus,
} from "../../components/icons";
import {
  convertUtcTimeToLocal,
  getTimezoneOffsetString,
} from "../../utils/datetime";
import { ScoutScheduleModal } from "../../components/calendar/ScoutScheduleModal";

export const ScoutScheduleCard: React.FC = () => {
  const {
    commentWindows,
    saveCommentWindows,
    nextScoutTime,
    timezone,
  } = useApp();

  const [isModalOpen, setIsModalOpen] = useState(false);

  const activeRuns = commentWindows.filter((w) => w.status === "active");
  const tzOffset = getTimezoneOffsetString(timezone);

  const handleToggle = async (id: string) => {
    const updated = commentWindows.map((win) => {
      if (win.id === id) {
        return {
          ...win,
          status: (win.status === "active" ? "paused" : "active") as
            | "active"
            | "paused",
        };
      }
      return win;
    });
    await saveCommentWindows(updated);
  };

  return (
    <>
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              Autonomous Scout Cadence &amp; Runs
            </h2>
            <span className="font-label-sm text-[11px] text-on-surface-variant font-normal">
              Timeline discovery frequency &amp; edge triggers
            </span>
          </div>
        </div>

        <div className="p-4 rounded-lg border border-outline/40 bg-surface-container-low flex flex-col gap-3.5 shadow-2xs">
          {/* Telemetry & Next Scout Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 p-3 rounded-md bg-surface-container-lowest border border-outline/50 shadow-2xs">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0">
                <Lightning size={16} weight="fill" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-on-surface flex items-center gap-1.5">
                  <span>{activeRuns.length} Active Scout Run{activeRuns.length !== 1 ? "s" : ""}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant">
                    {commentWindows.length} Total Configured
                  </span>
                </span>
                <span className="text-[11px] text-on-surface-variant flex items-center gap-1">
                  <Clock size={12} className="text-primary inline shrink-0" />
                  <span>Next Run: <strong className="text-on-surface font-medium">{nextScoutTime}</strong></span>
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-mono text-on-surface-variant px-2 py-0.5 rounded bg-surface-container border border-outline/40">
                Timezone: {timezone} ({tzOffset})
              </span>
            </div>
          </div>

          {/* List of Configured Runs */}
          <div className="flex flex-col gap-2">
            {commentWindows.map((win, idx) => {
              const isToggled = win.status === "active";
              const localStart =
                win.local_start_time || convertUtcTimeToLocal(win.start_time, timezone);
              const localEnd =
                win.local_end_time || convertUtcTimeToLocal(win.end_time, timezone);

              return (
                <div
                  key={win.id}
                  className={`flex items-center justify-between p-2.5 rounded-md transition-colors border ${
                    isToggled
                      ? "bg-surface-container-lowest border-outline/50"
                      : "bg-surface-container-lowest/60 border-outline/30 opacity-70"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 pr-2">
                    <span className="w-5 h-5 rounded-full bg-surface-container-high text-[10px] font-mono font-semibold flex items-center justify-center text-on-surface-variant shrink-0">
                      {idx + 1}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-on-surface truncate">
                          {win.title}
                        </span>
                        {!isToggled && (
                          <span className="text-[10px] font-mono px-1 rounded bg-surface-container-highest text-on-surface-variant">
                            Paused
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-on-surface-variant truncate">
                        Focus: {win.topic_filter || "General Timeline"} • Days: {win.days.join(", ")}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div
                      className="flex flex-col text-right font-mono text-[11px] text-on-surface font-medium tabular-nums"
                      title={`UTC: ${win.start_time} - ${win.end_time}`}
                    >
                      <span>{localStart} - {localEnd}</span>
                    </div>

                    {/* Toggle button */}
                    <button
                      type="button"
                      aria-label={`Toggle ${win.title}`}
                      onClick={() => handleToggle(win.id)}
                      className={`w-8 h-4.5 rounded-full p-0.5 transition-colors flex items-center cursor-pointer ${
                        isToggled
                          ? "bg-primary justify-end"
                          : "bg-surface-container-highest justify-start"
                      }`}
                    >
                      <div className="w-3.5 h-3.5 rounded-full bg-white shadow-2xs" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Action Footer */}
          <div className="flex items-center justify-between pt-1 border-t border-outline/30 text-[11px] text-on-surface-variant">
            <span>
              Scout runs automatically triage feeds and draft human-in-the-loop proposals to Telegram.
            </span>
            <button
              type="button"
              data-testid="settings-configure-scout-btn"
              onClick={() => setIsModalOpen(true)}
              className="text-xs text-primary hover:underline font-medium flex items-center gap-1 cursor-pointer"
            >
              <Plus size={12} weight="bold" />
              <span>Configure Runs</span>
            </button>
          </div>
        </div>
      </div>

      <ScoutScheduleModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        commentWindows={commentWindows}
        onSave={saveCommentWindows}
        timezone={timezone}
      />
    </>
  );
};
