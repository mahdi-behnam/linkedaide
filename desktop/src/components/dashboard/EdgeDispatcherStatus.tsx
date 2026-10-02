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
    <section className="bg-surface-container-lowest rounded-xl p-5 border border-outline shadow-2xs flex flex-col gap-4">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Globe size={17} weight="bold" />
          </div>
          <h2 className="headline-sm text-on-surface">Edge Dispatcher Status</h2>
        </div>
        <span className="code-sm px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-medium border border-outline">
          Cloudflare Worker
        </span>
      </div>

      {/* Native Things 3 Activity Chart Pane */}
      <div className="p-4 rounded-xl bg-surface-container-low border border-outline flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
            24h Invocations &amp; Latency
          </span>
          <span className="code-sm text-tertiary font-medium">99.98% Healthy</span>
        </div>

        {/* Clean Native Bar Chart */}
        <div className="h-20 w-full flex items-end gap-1.5 pt-2 pb-1">
          {bars.map((bar, i) => (
            <div
              key={i}
              title={`${bar.time} - ${bar.req}`}
              style={{ height: bar.height }}
              className={`flex-1 rounded-t-sm transition-all duration-300 ${
                bar.isCurrent
                  ? "bg-primary shadow-xs"
                  : "bg-primary/25 hover:bg-primary/70"
              }`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between text-on-surface-variant code-sm border-t border-outline/70 pt-2">
          <span>02:00</span>
          <span>08:00</span>
          <span>14:00</span>
          <span className="text-on-surface font-semibold">20:00 (Now)</span>
        </div>
      </div>

      {/* Health Metric Breakdown List */}
      <div className="flex flex-col divide-y divide-outline/60 body-md">
        <div className="py-2.5 flex items-center justify-between">
          <span className="text-on-surface-variant">Average Dispatch Latency</span>
          <span className="code-sm font-semibold text-on-surface">{latencyMs} ms</span>
        </div>
        <div className="py-2.5 flex items-center justify-between">
          <span className="text-on-surface-variant">KV Edge Read Time</span>
          <span className="code-sm font-semibold text-on-surface">{kvReadTimeMs} ms</span>
        </div>
        <div className="py-2.5 flex items-center justify-between">
          <span className="text-on-surface-variant">Telegram Webhook Gateway</span>
          <span className="code-sm text-tertiary flex items-center gap-1.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse" />
            Active (0 dropped)
          </span>
        </div>
      </div>
    </section>
  );
};
