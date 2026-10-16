import React, { useState, useMemo } from "react";
import { useApp } from "../context/AppContext";
import type { AuditEntry } from "../types";
import {
  ChartLineUp,
  CheckCircle,
  ChatTeardropDots,
  Clock,
  Sparkle,
  ArrowClockwise,
} from "../components/icons";
import { KpiMetricCard } from "../components/analytics/KpiMetricCard";
import {
  EngagementHeatmap,
  TimeBlock,
} from "../components/analytics/EngagementHeatmap";
import {
  TopicPillarDistribution,
  TopicPillarMetric,
} from "../components/analytics/TopicPillarDistribution";
import {
  HighImpactCommentsTable,
  HighImpactComment,
} from "../components/analytics/HighImpactCommentsTable";

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const TIME_BLOCKS: TimeBlock[] = [
  { id: "morning", label: "Morning", hours: "08:00 - 11:00" },
  { id: "midday", label: "Midday", hours: "11:00 - 14:00" },
  { id: "afternoon", label: "Afternoon", hours: "14:00 - 17:00" },
  { id: "evening", label: "Evening", hours: "17:00 - 20:00" },
];

export const DEFAULT_HEATMAP_DATA: Record<string, number[]> = {
  Mon: [2, 3, 2, 1],
  Tue: [3, 3, 2, 1],
  Wed: [2, 3, 3, 1],
  Thu: [3, 3, 3, 2],
  Fri: [2, 2, 1, 0],
  Sat: [0, 1, 1, 0],
  Sun: [1, 2, 2, 1],
};

export const DEFAULT_HEATMAP_RATES: Record<string, string[]> = {
  Mon: ["58%", "82%", "64%", "31%"],
  Tue: ["74%", "88%", "69%", "35%"],
  Wed: ["65%", "91%", "78%", "29%"],
  Thu: ["81%", "94%", "83%", "46%"],
  Fri: ["60%", "67%", "38%", "18%"],
  Sat: ["15%", "34%", "29%", "12%"],
  Sun: ["38%", "54%", "62%", "33%"],
};

function deriveTopicPillar(entry: { targetHeadline?: string; draftExcerpt?: string }) {
  const text = `${entry.targetHeadline || ""} ${entry.draftExcerpt || ""}`.toLowerCase();
  if (/distributed|kv|cache|cloud|infra|state/i.test(text)) {
    return { name: "Distributed Systems", tag: "Infra & Architecture" };
  }
  if (/ai|llm|model|reasoning|nim|agent|verification/i.test(text)) {
    return { name: "Enterprise AI", tag: "Applied LLM" };
  }
  if (/playwright|browser|scrape|automation/i.test(text)) {
    return { name: "Browser Automation", tag: "Playwright & Scraping" };
  }
  if (/cloudflare|worker|edge/i.test(text)) {
    return { name: "Cloudflare Edge", tag: "Edge KV & Workers" };
  }
  return { name: "Agent Architecture", tag: "HITL Systems" };
}

export interface AnalyticsViewProps {
  initialComments?: HighImpactComment[];
  initialTopicPillars?: TopicPillarMetric[];
  initialHeatmapData?: Record<string, number[]>;
  initialHeatmapRates?: Record<string, string[]>;
  initialAuditEntries?: AuditEntry[];
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({
  initialComments,
  initialTopicPillars,
  initialHeatmapData,
  initialHeatmapRates,
  initialAuditEntries,
}) => {
  const { auditEntries: contextAuditEntries, refreshState, formatDate } = useApp();
  const auditEntries = initialAuditEntries ?? contextAuditEntries;
  const [selectedTimeframe, setSelectedTimeframe] = useState<"7d" | "30d" | "all">("7d");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      if (refreshState) {
        await refreshState();
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const executedSuccessEntries = useMemo(() => {
    return auditEntries.filter((e) => e.status === "executed_success");
  }, [auditEntries]);

  const hasExecutedData = executedSuccessEntries.length > 0;

  // Combine real executed audit items from state store
  const executedAuditItems: HighImpactComment[] = useMemo(() => {
    return auditEntries
      .filter((e) => e.status === "executed_success" && (e.targetAuthor || e.draftExcerpt))
      .slice(0, 10)
      .map((e) => ({
        id: e.id,
        author: e.targetAuthor || "Industry Leader",
        headline: e.targetHeadline || "Engineering Leader",
        topic: deriveTopicPillar(e).name,
        commentExcerpt: e.draftExcerpt || "High-resonance architectural commentary.",
        status: "Executed",
        timestamp: e.executedAt ? formatDate(e.executedAt) : "Recent",
      }));
  }, [auditEntries, formatDate]);

  const displayComments = useMemo(() => {
    if (initialComments !== undefined) return initialComments;
    return executedAuditItems;
  }, [initialComments, executedAuditItems]);

  const topicPillars: TopicPillarMetric[] = useMemo(() => {
    if (initialTopicPillars !== undefined) return initialTopicPillars;
    if (executedSuccessEntries.length === 0) return [];

    const groupMap = new Map<string, { tag: string; count: number }>();
    for (const e of executedSuccessEntries) {
      const { name, tag } = deriveTopicPillar(e);
      const cur = groupMap.get(name) || { tag, count: 0 };
      cur.count += 1;
      groupMap.set(name, cur);
    }

    const total = executedSuccessEntries.length;
    return Array.from(groupMap.entries()).map(([name, { tag, count }]) => {
      const percentage = Math.min(100, Math.round((count / total) * 100));
      return {
        name,
        tag,
        commentsCount: count,
        percentage,
      };
    });
  }, [executedSuccessEntries, initialTopicPillars]);

  // Dynamically compute heatmap matrix from executed audit entries
  const { calculatedHeatmapData, calculatedHeatmapRates } = useMemo(() => {
    const data: Record<string, number[]> = {
      Mon: [0, 0, 0, 0],
      Tue: [0, 0, 0, 0],
      Wed: [0, 0, 0, 0],
      Thu: [0, 0, 0, 0],
      Fri: [0, 0, 0, 0],
      Sat: [0, 0, 0, 0],
      Sun: [0, 0, 0, 0],
    };
    const counts: Record<string, number[]> = {
      Mon: [0, 0, 0, 0],
      Tue: [0, 0, 0, 0],
      Wed: [0, 0, 0, 0],
      Thu: [0, 0, 0, 0],
      Fri: [0, 0, 0, 0],
      Sat: [0, 0, 0, 0],
      Sun: [0, 0, 0, 0],
    };

    const DAY_MAP = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    for (const e of executedSuccessEntries) {
      const d = new Date(e.executedAt || e.decidedAt);
      if (isNaN(d.getTime())) continue;
      const day = DAY_MAP[d.getDay()];
      const hour = d.getHours();
      let blockIdx = 0;
      if (hour >= 8 && hour < 11) blockIdx = 0;
      else if (hour >= 11 && hour < 14) blockIdx = 1;
      else if (hour >= 14 && hour < 17) blockIdx = 2;
      else blockIdx = 3;

      if (counts[day]) {
        counts[day][blockIdx] += 1;
      }
    }

    let maxCount = 0;
    for (const day of Object.keys(counts)) {
      for (let b = 0; b < 4; b++) {
        if (counts[day][b] > maxCount) maxCount = counts[day][b];
      }
    }

    const rates: Record<string, string[]> = {
      Mon: ["0%", "0%", "0%", "0%"],
      Tue: ["0%", "0%", "0%", "0%"],
      Wed: ["0%", "0%", "0%", "0%"],
      Thu: ["0%", "0%", "0%", "0%"],
      Fri: ["0%", "0%", "0%", "0%"],
      Sat: ["0%", "0%", "0%", "0%"],
      Sun: ["0%", "0%", "0%", "0%"],
    };

    for (const day of Object.keys(counts)) {
      for (let b = 0; b < 4; b++) {
        const c = counts[day][b];
        if (c === 0) {
          data[day][b] = 0;
          rates[day][b] = "0%";
        } else {
          data[day][b] = maxCount <= 1 ? 1 : Math.min(3, Math.ceil((c / maxCount) * 3));
          const total = executedSuccessEntries.length;
          const pct = Math.round((c / (total || 1)) * 100);
          rates[day][b] = `${pct}%`;
        }
      }
    }

    return { calculatedHeatmapData: data, calculatedHeatmapRates: rates };
  }, [executedSuccessEntries]);

  const hasHeatmapData = Boolean(
    initialHeatmapData || (executedSuccessEntries.length > 0)
  );

  const heatmapData = initialHeatmapData ?? calculatedHeatmapData;
  const heatmapRates = initialHeatmapRates ?? calculatedHeatmapRates;

  const kpiExecuted = hasExecutedData ? `${executedSuccessEntries.length} Actions` : "--";
  const kpiApprovalRate = hasExecutedData
    ? `${Math.round((executedSuccessEntries.length / auditEntries.length) * 100)}%`
    : "0%";
  const kpiVelocity = useMemo(() => {
    if (!hasExecutedData) return "--";
    const withTimes = executedSuccessEntries.filter(
      (e) => e.decidedAt && e.executedAt
    );
    if (withTimes.length === 0) {
      return "--";
    }
    const diffsSec = withTimes.map((e) => {
      const diffMs = new Date(e.executedAt!).getTime() - new Date(e.decidedAt).getTime();
      return Math.max(1, Math.round(diffMs / 1000));
    });
    const avgSec = Math.round(diffsSec.reduce((a, b) => a + b, 0) / diffsSec.length);
    return `${avgSec}s`;
  }, [hasExecutedData, executedSuccessEntries]);
  const kpiFocusAreas = hasExecutedData
    ? `${topicPillars.length} Pillar${topicPillars.length === 1 ? "" : "s"}`
    : "--";

  return (
    <div className="flex flex-col gap-5 max-w-7xl mx-auto">
      {/* View Header & Timeframe Segmented Control */}
      <header className="flex flex-col justify-between gap-4 pb-3 border-b border-outline/60 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md border border-outline/50 bg-surface-container-high text-primary shadow-2xs">
              <ChartLineUp size={16} weight="bold" />
            </div>
            <h1 className="text-sm font-semibold tracking-tight text-on-surface">
              LinkedIn Growth Analytics
            </h1>
            <span className="font-mono text-[11px] text-on-surface-variant font-medium">
              Live Analytics
            </span>
          </div>
          <p className="mt-1 text-[11px] text-on-surface-variant">
            Real-time engagement telemetry, operator approval metrics, and time-of-day execution activity.
          </p>
        </div>

        {/* Action Bar: Timeframe Segmented Control & Refresh */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          {/* Segmented Control with bg-zinc-800 preserved for testing */}
          <div className="flex rounded-md border border-outline/50 bg-surface-container-low p-0.5 shadow-2xs">
            {(["7d", "30d", "all"] as const).map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setSelectedTimeframe(tf)}
                className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors ${
                  selectedTimeframe === tf
                    ? "border border-zinc-700 bg-zinc-800 text-white shadow-2xs"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                }`}
              >
                {tf === "7d" ? "7 Days" : tf === "30d" ? "30 Days" : "All Time"}
              </button>
            ))}
          </div>

          <button
            type="button"
            data-testid="refresh-analytics-btn"
            onClick={handleRefresh}
            title="Refresh engagement metrics"
            className="flex h-7 w-7 items-center justify-center rounded-md border border-outline/60 bg-surface-container-lowest text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface shadow-2xs"
          >
            <ArrowClockwise
              size={14}
              weight="bold"
              className={isRefreshing ? "animate-spin text-primary" : ""}
            />
          </button>
        </div>
      </header>

      {/* Top Metrics Row: 4 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* KPI 1: Executed Actions */}
        <KpiMetricCard
          testId="kpi-reach"
          title="Executed Actions"
          value={kpiExecuted}
          trendText={hasExecutedData ? "100% verified" : undefined}
          hasData={hasExecutedData}
          subtitle="Approved & verified comments and posts"
          icon={<CheckCircle size={15} weight="bold" />}
          iconColorClass="text-tertiary"
        />

        {/* KPI 2: Approval Rate */}
        <KpiMetricCard
          testId="kpi-reply-rate"
          title="Approval Rate"
          value={kpiApprovalRate}
          trendText={hasExecutedData ? "Active gate" : undefined}
          hasData={hasExecutedData}
          subtitle="% of suggestions approved vs rejected"
          icon={<ChatTeardropDots size={15} weight="bold" />}
          iconColorClass="text-primary"
        />

        {/* KPI 3: Approval Velocity */}
        <KpiMetricCard
          testId="kpi-velocity"
          title="Approval Velocity"
          value={kpiVelocity}
          trendText={hasExecutedData ? "Review speed" : undefined}
          hasData={hasExecutedData}
          subtitle="Average operator review-to-execution latency"
          icon={<Clock size={15} weight="bold" />}
          iconColorClass="text-secondary"
        />

        {/* KPI 4: Active Focus Areas */}
        <KpiMetricCard
          testId="kpi-engagement-score"
          title="Active Focus Areas"
          value={kpiFocusAreas}
          trendText={hasExecutedData ? "Distribution" : undefined}
          hasData={hasExecutedData}
          subtitle={
            hasExecutedData
              ? `${topicPillars.length} distinct topic pillars targeted`
              : "Topic pillars targeted by the agent"
          }
          icon={<Sparkle size={15} weight="bold" />}
          iconColorClass="text-amber-500"
        />
      </section>

      {/* Middle Row: Heatmap Matrix & Topic Pillar Distribution */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
        {/* Heatmap (7 cols) */}
        <EngagementHeatmap
          days={DAYS}
          timeBlocks={TIME_BLOCKS}
          heatmapData={heatmapData}
          heatmapRates={heatmapRates}
          hasHeatmapData={hasHeatmapData}
        />

        {/* Topic Pillars (5 cols) */}
        <TopicPillarDistribution topicPillars={topicPillars} />
      </div>

      {/* Bottom Section: Recent High-Impact Comments Table */}
      <HighImpactCommentsTable comments={displayComments} />
    </div>
  );
};
