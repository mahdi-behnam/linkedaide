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
      className="rounded-lg border border-outline/70 bg-surface-container-lowest p-4 shadow-2xs lg:col-span-7 flex flex-col gap-2.5"
    >
      <div className="flex flex-col justify-between gap-1 border-b border-outline/50 pb-2.5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-tertiary/10 text-tertiary">
            <Calendar size={15} weight="bold" />
          </div>
          <h2 className="text-xs font-semibold text-on-surface">
            Weekly Time-of-Day Engagement Matrix
          </h2>
        </div>
        <span className="font-mono text-[10px] text-on-surface-variant">
          7 days x 4 time blocks
        </span>
      </div>

      <p className="text-[11px] text-on-surface-variant">
        Algorithmic peak engagement hours for author responses and feed traction.
      </p>

      {hasHeatmapData ? (
        <>
          {/* Matrix Grid */}
          <div className="mt-1 overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px]">
              <thead>
                <tr className="border-b border-outline/50 text-on-surface-variant">
                  <th className="pb-1.5 font-medium">Day</th>
                  {timeBlocks.map((tb) => (
                    <th key={tb.id} className="pb-1.5 text-center font-medium">
                      <div className="text-on-surface text-[11px] font-semibold">{tb.label}</div>
                      <div className="text-[10px] text-on-surface-variant/70 font-normal">
                        {tb.hours}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline/40">
                {days.map((day) => {
                  const dayLevels = heatmapData[day] || [0, 0, 0, 0];
                  const dayRates = heatmapRates[day] || ["0%", "0%", "0%", "0%"];
                  return (
                    <tr key={day} className="hover:bg-surface-container-low/60 transition-colors">
                      <td className="py-2 font-medium text-on-surface">{day}</td>
                      {dayLevels.map((lvl, idx) => {
                        const rate = dayRates[idx];
                        let cellStyle =
                          "border-outline/50 bg-surface-container-low/70 text-on-surface-variant/60";
                        if (lvl === 1) {
                          cellStyle =
                            "border-tertiary/30 bg-tertiary/10 text-tertiary font-medium";
                        } else if (lvl === 2) {
                          cellStyle =
                            "border-tertiary/45 bg-tertiary/20 text-tertiary font-semibold";
                        } else if (lvl === 3) {
                          cellStyle =
                            "border-tertiary/60 bg-tertiary/35 text-on-surface font-bold shadow-2xs";
                        }

                        return (
                          <td key={idx} className="p-1 text-center">
                            <div
                              data-testid={`heatmap-cell-${day}-${timeBlocks[idx].id}`}
                              title={`${day} ${timeBlocks[idx].label} (${timeBlocks[idx].hours}): ${rate} response rate`}
                              className={`mx-auto flex h-7 w-full max-w-[76px] items-center justify-center rounded-md border transition-colors tabular-nums ${cellStyle}`}
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
          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-outline/50 pt-2.5 text-[10px] text-on-surface-variant">
            <span className="font-mono text-[10px] text-on-surface-variant">Engagement Intensity:</span>
            <div className="flex items-center gap-3 font-mono">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs border border-outline bg-surface-container-low" />
                <span>Off-Peak (&lt;25%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs border border-tertiary/30 bg-tertiary/10" />
                <span>Moderate (25-50%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs border border-tertiary/45 bg-tertiary/20" />
                <span>High Signal (50-75%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs border border-tertiary/60 bg-tertiary/35" />
                <span className="text-tertiary font-semibold">Peak Resonance (&gt;75%)</span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div
          data-testid="heatmap-empty"
          className="mt-2 flex h-52 flex-col items-center justify-center rounded-md border border-dashed border-outline bg-surface-container-low/40 p-5 text-center"
        >
          <Calendar size={24} className="text-on-surface-variant/50 mb-1.5" />
          <p className="text-xs font-semibold text-on-surface">No engagement data recorded yet.</p>
          <p className="mt-0.5 text-[11px] text-on-surface-variant max-w-xs">
            Algorithmic peak engagement hours will populate as comments are executed and tracked.
          </p>
        </div>
      )}
    </div>
  );
};
