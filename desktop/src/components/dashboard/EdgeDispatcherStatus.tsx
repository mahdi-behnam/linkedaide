import React from "react";
import { Globe } from "../icons";

export interface EdgeDispatcherStatusProps {
  workerUrl?: string;
  latencyMs?: number;
  kvReadTimeMs?: number;
}

export const EdgeDispatcherStatus: React.FC<EdgeDispatcherStatusProps> = ({
  latencyMs = 142,
  kvReadTimeMs = 4.2,
}) => {
  const bars = [
    { time: "02:00 UTC", req: "140 req", height: "38%" },
    { time: "04:00 UTC", req: "180 req", height: "52%" },
    { time: "06:00 UTC", req: "145 req", height: "40%" },
    { time: "08:00 UTC", req: "240 req", height: "65%" },
    { time: "10:00 UTC", req: "310 req", height: "80%" },
    { time: "12:00 UTC", req: "390 req", height: "94%" },
    { time: "14:00 UTC", req: "280 req", height: "72%" },
    { time: "16:00 UTC", req: "220 req", height: "60%" },
    { time: "18:00 UTC", req: "165 req", height: "45%" },
    { time: "20:00 UTC (Current)", req: "215 req", height: "58%", isCurrent: true },
  ];

  return (
    <section className="bg-surface-bright rounded-lg p-4 border border-outline shadow-2xs flex flex-col gap-3.5">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Globe size={14} weight="bold" />
          </div>
          <h2 className="text-sm font-semibold text-on-surface">Edge Dispatcher Status</h2>
        </div>
        <span className="text-[11px] px-1.5 py-0.2 rounded bg-surface-container-high text-on-surface-variant font-medium border border-outline font-sans">
          Cloudflare Worker
        </span>
      </div>

      {/* Activity Chart Pane */}
      <div className="p-3 rounded-md bg-surface-container-low border border-outline flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-on-surface-variant">
            24h Invocations &amp; Latency
          </span>
          <span className="text-[11px] text-tertiary font-medium">All Systems Operational</span>
        </div>

        {/* Clean Native Bar Chart */}
        <div className="h-16 w-full flex items-end gap-1.5 pt-2 pb-1">
          {bars.map((bar, i) => (
            <div
              key={i}
              title={`${bar.time} - ${bar.req}`}
              style={{ height: bar.height }}
              className={`flex-1 rounded-t-xs transition-colors ${
                bar.isCurrent
                  ? "bg-primary"
                  : "bg-primary/25 hover:bg-primary/60"
              }`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between text-on-surface-variant text-[11px] border-t border-outline/70 pt-1.5 font-sans">
          <span>02:00</span>
          <span>08:00</span>
          <span>14:00</span>
          <span className="text-on-surface font-medium">20:00 (Now)</span>
        </div>
      </div>

      {/* Health Metric Breakdown List */}
      <div className="flex flex-col divide-y divide-outline/60 text-xs">
        <div className="py-2 flex items-center justify-between">
          <span className="text-on-surface-variant">Average Dispatch Latency</span>
          <span className="font-medium text-on-surface tabular-nums">{latencyMs} ms</span>
        </div>
        <div className="py-2 flex items-center justify-between">
          <span className="text-on-surface-variant">KV Edge Read Time</span>
          <span className="font-medium text-on-surface tabular-nums">{kvReadTimeMs} ms</span>
        </div>
        <div className="py-2 flex items-center justify-between">
          <span className="text-on-surface-variant">Telegram Webhook Gateway</span>
          <span className="text-tertiary flex items-center gap-1.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary" />
            Active (0 dropped)
          </span>
        </div>
      </div>
    </section>
  );
};
