import React, { useState } from "react";
import { AutomatedCommentWindow } from "../../types";
import { Lightning, PencilSimple } from "../icons";
import { useApp } from "../../context/AppContext";
import {
  convertUtcTimeToLocal,
  getTimezoneOffsetString,
} from "../../utils/datetime";
import { ScoutScheduleModal } from "./ScoutScheduleModal";

interface ScoutScheduleCardProps {
  commentWindows: AutomatedCommentWindow[];
}

export const ScoutScheduleCard: React.FC<ScoutScheduleCardProps> = ({
  commentWindows,
}) => {
  const { timezone, saveCommentWindows } = useApp();
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  const tzOffset = getTimezoneOffsetString(timezone);

  return (
    <>
      <div className="flex flex-col gap-3 bg-surface-container-lowest p-4 rounded-lg border border-outline/70 shadow-2xs">
        <div className="flex items-center justify-between pb-1 border-b border-outline/50">
          <div className="flex items-center gap-2">
            <Lightning size={16} weight="fill" className="text-primary" />
            <h3 className="text-xs font-semibold text-on-surface">
              Automated Comment Scout Schedule
            </h3>
          </div>

          <button
            type="button"
            data-testid="edit-scout-schedule-btn"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium text-primary hover:bg-primary/10 transition-colors border border-primary/20"
          >
            <PencilSimple size={12} weight="bold" />
            <span>Configure Schedule</span>
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {commentWindows.map((win) => {
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
                    ? "bg-surface-container-low hover:bg-surface-container border-outline/50"
                    : "bg-surface-container-lowest border-outline/30 opacity-70"
                }`}
              >
                <div className="flex flex-col min-w-0 pr-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs font-semibold text-on-surface truncate"
                      title={win.title}
                    >
                      {win.title}
                    </span>
                    {!isToggled && (
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface-container-highest text-on-surface-variant">
                        Paused
                      </span>
                    )}
                  </div>
                  <span
                    className="text-[11px] text-on-surface-variant truncate"
                    title={`Target: ${win.topic_filter}`}
                  >
                    Target: {win.topic_filter || "All Focus Areas"}
                  </span>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div
                    className="flex flex-col text-right"
                    title={`UTC Schedule: ${win.start_time} - ${win.end_time} UTC`}
                  >
                    <span className="font-mono text-[10px] text-on-surface font-medium tabular-nums">
                      {localStart} - {localEnd}{" "}
                      <span className="text-on-surface-variant text-[9px]">
                        ({tzOffset})
                      </span>
                    </span>
                    <span className="text-[10px] text-on-surface-variant">
                      Runs: {win.days.slice(0, 3).join(", ")}
                      {win.days.length > 3 ? "..." : ""}
                    </span>
                  </div>

                  {/* Switch toggle */}
                  <button
                    type="button"
                    aria-label={`Toggle scout window ${win.title}`}
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
