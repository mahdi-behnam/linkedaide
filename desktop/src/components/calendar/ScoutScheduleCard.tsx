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
    <div className="flex flex-col gap-3 bg-surface-container-lowest p-4 rounded-lg border border-outline/70 shadow-2xs">
      <div className="flex items-center justify-between pb-1 border-b border-outline/50">
        <div className="flex items-center gap-2">
          <Lightning size={16} weight="fill" className="text-primary" />
          <h3 className="text-xs font-semibold text-on-surface">
            Automated Comment Scout Schedule
          </h3>
        </div>
        <span className="text-[10px] px-1.5 py-0.2 rounded-[4px] bg-secondary-container/20 text-on-surface font-medium border border-outline/40">
          Recurring Cadence
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {commentWindows.map((win, idx) => {
          const isToggled = toggleState[win.id] ?? (idx < 2);

          return (
            <div
              key={win.id}
              className="flex items-center justify-between p-2.5 rounded-md bg-surface-container-low hover:bg-surface-container transition-colors border border-outline/50"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    isToggled ? "bg-tertiary" : "bg-outline-variant"
                  }`}
                  title={isToggled ? "Active" : "Standby"}
                />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold text-on-surface truncate">
                    {win.title}
                  </span>
                  <span className="text-[11px] text-on-surface-variant truncate">
                    Target: {win.topic_filter}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <div className="flex flex-col text-right">
                  <span className="font-mono text-[10px] text-on-surface font-medium tabular-nums">
                    {win.start_time} - {win.end_time} UTC
                  </span>
                  <span className="text-[10px] text-on-surface-variant">
                    Runs: {win.days.slice(0, 3).join(", ")}{win.days.length > 3 ? "..." : ""}
                  </span>
                </div>

                {/* Switch toggle */}
                <button
                  type="button"
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
  );
};
