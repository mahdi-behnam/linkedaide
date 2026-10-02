import React, { useState } from "react";
import { AutomatedCommentWindow } from "../../types";
import { Lightning } from "../icons";

interface ScoutScheduleCardProps {
  commentWindows: AutomatedCommentWindow[];
}

export const ScoutScheduleCard: React.FC<ScoutScheduleCardProps> = ({
  commentWindows,
}) => {
  const [toggleState, setToggleState] = useState<Record<string, boolean>>({
    "win-001": true,
    "win-002": true,
    "win-003": false,
  });

  const handleToggle = (id: string) => {
    setToggleState((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  return (
    <div className="flex flex-col gap-3.5 bg-surface-container-lowest p-5 rounded-2xl border border-surface-container-high shadow-xs">
      <div className="flex items-center justify-between pb-1 border-b border-surface-container-high/60">
        <div className="flex items-center gap-2">
          <Lightning size={18} weight="fill" className="text-primary" />
          <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">
            Automated Comment Scout Schedule
          </h3>
        </div>
        <span className="font-label-sm text-label-sm px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-medium">
          Recurring Cadence
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        {commentWindows.map((win, idx) => {
          const isToggled = toggleState[win.id] ?? (idx < 2);

          return (
            <div
              key={win.id}
              className="flex items-center justify-between p-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors border border-surface-container-high/50"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                    isToggled ? "bg-tertiary" : "bg-outline-variant"
                  }`}
                  title={isToggled ? "Active" : "Standby"}
                />
                <div className="flex flex-col min-w-0">
                  <span className="font-body-strong text-body-strong text-on-surface truncate">
                    {win.title}
                  </span>
                  <span className="font-body-md text-body-md text-on-surface-variant truncate">
                    Target: {win.topic_filter}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4 shrink-0">
                <div className="flex flex-col text-right">
                  <span className="font-code-sm text-code-sm text-on-surface font-medium">
                    {win.start_time} - {win.end_time} UTC
                  </span>
                  <span className="font-label-sm text-label-sm text-on-surface-variant">
                    Runs: {win.days.slice(0, 3).join(", ")}{win.days.length > 3 ? "..." : ""}
                  </span>
                </div>

                {/* Switch toggle */}
                <button
                  type="button"
                  onClick={() => handleToggle(win.id)}
                  className={`w-9 h-5 rounded-full p-0.5 transition-colors flex items-center cursor-pointer ${
                    isToggled
                      ? "bg-tertiary-container justify-end"
                      : "bg-surface-container-highest justify-start"
                  }`}
                >
                  <div className="w-4 h-4 rounded-full bg-white shadow-2xs" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
