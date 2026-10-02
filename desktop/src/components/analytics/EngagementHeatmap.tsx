import React from "react";
import { Calendar } from "../icons";

export interface TimeBlock {
  id: string;
  label: string;
  hours: string;
}

export interface EngagementHeatmapProps {
  days: string[];
  timeBlocks: TimeBlock[];
  heatmapData: Record<string, number[]>;
  heatmapRates: Record<string, string[]>;
  hasHeatmapData: boolean;
}

export const EngagementHeatmap: React.FC<EngagementHeatmapProps> = ({
  days,
  timeBlocks,
  heatmapData,
  heatmapRates,
  hasHeatmapData,
}) => {
  return (
    <div
      data-testid="heatmap-matrix"
      className="rounded-xl border border-outline bg-surface-container-lowest p-5 shadow-2xs lg:col-span-7 flex flex-col gap-3"
    >
      <div className="flex flex-col justify-between gap-1 border-b border-outline pb-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-tertiary/10 text-tertiary">
            <Calendar size={16} weight="bold" />
          </div>
          <h2 className="headline-sm text-on-surface">
            Weekly Time-of-Day Engagement Matrix
          </h2>
        </div>
        <span className="code-sm text-on-surface-variant">
          7 days x 4 time blocks
        </span>
      </div>

      <p className="body-md text-on-surface-variant">
        Algorithmic peak engagement hours for author responses and feed traction.
      </p>

      {hasHeatmapData ? (
        <>
          {/* Matrix Grid */}
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px]">
              <thead>
                <tr className="border-b border-outline text-on-surface-variant">
                  <th className="pb-2 font-medium">Day</th>
                  {timeBlocks.map((tb) => (
                    <th key={tb.id} className="pb-2 text-center font-medium">
                      <div className="text-on-surface font-semibold">{tb.label}</div>
                      <div className="text-[10px] text-on-surface-variant/70 font-normal">
                        {tb.hours}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline/50">
                {days.map((day) => {
                  const dayLevels = heatmapData[day] || [0, 0, 0, 0];
                  const dayRates = heatmapRates[day] || ["0%", "0%", "0%", "0%"];
                  return (
                    <tr key={day} className="hover:bg-surface-container-low/60 transition-colors">
                      <td className="py-2.5 font-medium text-on-surface">{day}</td>
                      {dayLevels.map((lvl, idx) => {
                        const rate = dayRates[idx];
                        let cellStyle =
                          "border-outline bg-surface-container-low/70 text-on-surface-variant/60";
                        if (lvl === 1) {
                          cellStyle =
                            "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium";
                        } else if (lvl === 2) {
                          cellStyle =
                            "border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold";
                        } else if (lvl === 3) {
                          cellStyle =
                            "border-emerald-400/60 bg-emerald-500/35 text-emerald-950 dark:text-emerald-100 font-bold shadow-2xs";
                        }

                        return (
                          <td key={idx} className="p-1 text-center">
                            <div
                              data-testid={`heatmap-cell-${day}-${timeBlocks[idx].id}`}
                              title={`${day} ${timeBlocks[idx].label} (${timeBlocks[idx].hours}): ${rate} response rate`}
                              className={`mx-auto flex h-8 w-full max-w-[80px] items-center justify-center rounded-lg border transition-all duration-150 hover:scale-[1.04] ${cellStyle}`}
                            >
                              <span>{rate}</span>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Heatmap Legend */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-outline pt-3 text-[10px] text-on-surface-variant">
            <span className="code-sm text-on-surface-variant">Engagement Intensity:</span>
            <div className="flex items-center gap-3 font-mono">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-outline bg-surface-container-low" />
                <span>Off-Peak (&lt;25%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-500/25 bg-emerald-500/10" />
                <span>Moderate (25-50%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-500/40 bg-emerald-500/20" />
                <span>High Signal (50-75%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-400/60 bg-emerald-500/35" />
                <span className="text-tertiary font-semibold">Peak Resonance (&gt;75%)</span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div
          data-testid="heatmap-empty"
          className="mt-2 flex h-60 flex-col items-center justify-center rounded-xl border border-dashed border-outline bg-surface-container-low/40 p-6 text-center"
        >
          <Calendar size={28} className="text-on-surface-variant/50 mb-2" />
          <p className="body-strong text-on-surface">No engagement data recorded yet.</p>
          <p className="mt-1 label-sm text-on-surface-variant max-w-xs">
            Algorithmic peak engagement hours will populate as comments are executed and tracked.
          </p>
        </div>
      )}
    </div>
  );
};
