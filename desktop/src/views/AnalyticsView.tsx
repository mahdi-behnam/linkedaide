import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import {
  ChartLineUp,
  Eye,
  ChatTeardropDots,
  TrendUp,
  Clock,
  Sparkle,
  Calendar,
  CheckCircle,
  ArrowClockwise,
} from "../components/icons";

interface TopicPillarMetric {
  name: string;
  tag: string;
  commentsCount: number;
  replyRate: string;
  impressions: string;
  resonanceScore: number;
  percentage: number;
}

interface HighImpactComment {
  id: string;
  author: string;
  headline: string;
  topic: string;
  commentExcerpt: string;
  authorReplied: boolean;
  reach: string;
  timestamp: string;
}

const TOPIC_PILLARS: TopicPillarMetric[] = [
  {
    name: "Distributed Systems",
    tag: "Infra & Architecture",
    commentsCount: 48,
    replyRate: "39.5%",
    impressions: "19.4k",
    resonanceScore: 96,
    percentage: 92,
  },
  {
    name: "Enterprise AI",
    tag: "Applied LLM",
    commentsCount: 41,
    replyRate: "36.8%",
    impressions: "16.2k",
    resonanceScore: 94,
    percentage: 85,
  },
  {
    name: "Browser Automation",
    tag: "Playwright & Scraping",
    commentsCount: 28,
    replyRate: "32.1%",
    impressions: "8.6k",
    resonanceScore: 88,
    percentage: 68,
  },
  {
    name: "Cloudflare Edge",
    tag: "Edge KV & Workers",
    commentsCount: 19,
    replyRate: "28.4%",
    impressions: "4.0k",
    resonanceScore: 82,
    percentage: 52,
  },
];

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const TIME_BLOCKS = [
  { id: "morning", label: "Morning", hours: "08:00 - 11:00" },
  { id: "midday", label: "Midday", hours: "11:00 - 14:00" },
  { id: "afternoon", label: "Afternoon", hours: "14:00 - 17:00" },
  { id: "evening", label: "Evening", hours: "17:00 - 20:00" },
];

// Engagement intensities for 7 days x 4 blocks
// 0: Off-Peak, 1: Moderate, 2: High Signal, 3: Peak Resonance
const HEATMAP_DATA: Record<string, number[]> = {
  Mon: [2, 3, 2, 1],
  Tue: [3, 3, 2, 1],
  Wed: [2, 3, 3, 1],
  Thu: [3, 3, 3, 2],
  Fri: [2, 2, 1, 0],
  Sat: [0, 1, 1, 0],
  Sun: [1, 2, 2, 1],
};

const HEATMAP_RATES: Record<string, string[]> = {
  Mon: ["58%", "82%", "64%", "31%"],
  Tue: ["74%", "88%", "69%", "35%"],
  Wed: ["65%", "91%", "78%", "29%"],
  Thu: ["81%", "94%", "83%", "46%"],
  Fri: ["60%", "67%", "38%", "18%"],
  Sat: ["15%", "34%", "29%", "12%"],
  Sun: ["38%", "54%", "62%", "33%"],
};

const HIGH_IMPACT_COMMENTS: HighImpactComment[] = [
  {
    id: "hic-1",
    author: "Satya Nadella",
    headline: "Chairman & CEO at Microsoft",
    topic: "Distributed Systems",
    commentExcerpt:
      "The compounding returns on autonomous verification pipelines highlight why deterministic guardrails matter more than raw model scale.",
    authorReplied: true,
    reach: "18.2k",
    timestamp: "Yesterday at 16:45",
  },
  {
    id: "hic-2",
    author: "Kelsey Hightower",
    headline: "Principal Technologist",
    topic: "Browser Automation",
    commentExcerpt:
      "Safe automation should always have a kill switch. If your bot needs autonomy without operator sign-off, you built a liability.",
    authorReplied: true,
    reach: "14.6k",
    timestamp: "2 days ago",
  },
  {
    id: "hic-3",
    author: "Andrej Karpathy",
    headline: "AI Researcher",
    topic: "Enterprise AI",
    commentExcerpt:
      "Deterministic state machines for tool-calling keep reasoning models grounded in reproducible workflows.",
    authorReplied: true,
    reach: "11.8k",
    timestamp: "3 days ago",
  },
  {
    id: "hic-4",
    author: "Mitchell Hashimoto",
    headline: "Founder & Infrastructure Engineer",
    topic: "Cloudflare Edge",
    commentExcerpt:
      "Edge persistence with sub-millisecond edge reads completely removes round-trip database overhead.",
    authorReplied: true,
    reach: "9.3k",
    timestamp: "Sep 26, 2026",
  },
];

export const AnalyticsView: React.FC = () => {
  const { auditEntries } = useApp();
  const [selectedTimeframe, setSelectedTimeframe] = useState<"7d" | "30d" | "all">("7d");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  // Combine static top performing comments with any executed audit items
  const executedAuditItems: HighImpactComment[] = auditEntries
    .filter((e) => e.status === "executed_success" && e.targetAuthor)
    .slice(0, 2)
    .map((e) => ({
      id: e.id,
      author: e.targetAuthor || "Industry Leader",
      headline: e.targetHeadline || "Engineering Leader",
      topic: "Distributed Systems",
      commentExcerpt: e.draftExcerpt || "High-resonance architectural commentary.",
      authorReplied: true,
      reach: "12.5k",
      timestamp: e.executedAt ? new Date(e.executedAt).toLocaleDateString() : "Recent",
    }));

  const displayComments = [
    ...HIGH_IMPACT_COMMENTS,
    ...executedAuditItems.filter((ea) => !HIGH_IMPACT_COMMENTS.some((hc) => hc.author === ea.author)),
  ];

  return (
    <div className="space-y-6">
      {/* View Header & Timeframe Selector */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <ChartLineUp size={18} weight="bold" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              LinkedIn Growth Analytics
            </h1>
            <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
              Live Cockpit
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Real-time engagement telemetry, author reply conversions, and time-of-day peak algorithmic windows.
          </p>
        </div>

        {/* Action Bar: Timeframe Pills & Refresh */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-zinc-800 bg-zinc-900/60 p-0.5">
            {(["7d", "30d", "all"] as const).map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setSelectedTimeframe(tf)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-all ${
                  selectedTimeframe === tf
                    ? "border border-zinc-700 bg-zinc-800 text-zinc-100 shadow-xs"
                    : "text-zinc-400 hover:text-zinc-200"
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
            className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900/60 text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-100 active:scale-[0.98]"
          >
            <ArrowClockwise
              size={14}
              className={isRefreshing ? "animate-spin text-emerald-400" : ""}
            />
          </button>
        </div>
      </div>

      {/* Top Metrics Row: KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* KPI 1: Estimated Reach / Impressions */}
        <div
          data-testid="kpi-reach"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-zinc-700"
        >
          <div className="flex items-center justify-between pb-2">
            <span className="font-mono text-[11px] font-medium text-zinc-400">
              Estimated Reach / Impressions
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-950 text-emerald-400">
              <Eye size={15} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-zinc-100">
              48.2k
            </span>
            <span className="inline-flex items-center gap-0.5 font-mono text-[11px] font-semibold text-emerald-400">
              <TrendUp size={12} weight="bold" />
              +14.2%
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            Total views across target posts engaged
          </p>
        </div>

        {/* KPI 2: Author Reply Conversion Rate */}
        <div
          data-testid="kpi-reply-rate"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-zinc-700"
        >
          <div className="flex items-center justify-between pb-2">
            <span className="font-mono text-[11px] font-medium text-zinc-400">
              Author Reply Conversion Rate
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-950 text-emerald-400">
              <ChatTeardropDots size={15} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-zinc-100">
              34.8%
            </span>
            <span className="inline-flex items-center gap-0.5 font-mono text-[11px] font-semibold text-emerald-400">
              <TrendUp size={12} weight="bold" />
              +5.6%
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            % of agent comments that received an author response
          </p>
        </div>

        {/* KPI 3: Approval Velocity */}
        <div
          data-testid="kpi-velocity"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-zinc-700"
        >
          <div className="flex items-center justify-between pb-2">
            <span className="font-mono text-[11px] font-medium text-zinc-400">
              Approval Velocity
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-950 text-cyan-400">
              <Clock size={15} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-zinc-100">
              42s
            </span>
            <span className="inline-flex items-center gap-0.5 font-mono text-[11px] font-semibold text-cyan-400">
              8s faster
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            Average time operator spent approving drafts
          </p>
        </div>

        {/* KPI 4: Topic Engagement Score */}
        <div
          data-testid="kpi-engagement-score"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-zinc-700"
        >
          <div className="flex items-center justify-between pb-2">
            <span className="font-mono text-[11px] font-medium text-zinc-400">
              Topic Engagement Score
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 bg-zinc-950 text-amber-400">
              <Sparkle size={15} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-zinc-100">
              94/100
            </span>
            <span className="rounded bg-amber-500/10 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-amber-300">
              Top 2%
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            94/100 high-signal score based on comment resonance
          </p>
        </div>
      </div>

      {/* Cockpit Middle Row: Heatmap Matrix & Topic Pillar Distribution */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Weekly Time-of-Day Engagement Matrix (7 cols) */}
        <div
          data-testid="heatmap-matrix"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-7"
        >
          <div className="flex flex-col justify-between gap-1 border-b border-zinc-800/80 pb-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <Calendar size={16} className="text-emerald-400" />
              <h2 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
                Weekly Time-of-Day Engagement Matrix
              </h2>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">
              7 days x 4 time blocks
            </span>
          </div>

          <p className="mt-2 text-xs text-zinc-400">
            Algorithmic peak engagement hours for author responses and feed traction.
          </p>

          {/* Matrix Grid */}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px]">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="pb-2 font-medium">Day</th>
                  {TIME_BLOCKS.map((tb) => (
                    <th key={tb.id} className="pb-2 text-center font-medium">
                      <div className="text-zinc-300">{tb.label}</div>
                      <div className="text-[9px] text-zinc-500">{tb.hours}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {DAYS.map((day) => {
                  const dayLevels = HEATMAP_DATA[day] || [0, 0, 0, 0];
                  const dayRates = HEATMAP_RATES[day] || ["0%", "0%", "0%", "0%"];
                  return (
                    <tr key={day} className="hover:bg-zinc-800/30">
                      <td className="py-2.5 font-medium text-zinc-300">{day}</td>
                      {dayLevels.map((lvl, idx) => {
                        const rate = dayRates[idx];
                        let cellStyle =
                          "border-zinc-800/80 bg-zinc-900/40 text-zinc-500";
                        if (lvl === 1) {
                          cellStyle =
                            "border-emerald-500/20 bg-emerald-500/10 text-emerald-400";
                        } else if (lvl === 2) {
                          cellStyle =
                            "border-emerald-500/40 bg-emerald-500/25 text-emerald-300 font-semibold";
                        } else if (lvl === 3) {
                          cellStyle =
                            "border-emerald-400/60 bg-emerald-500/45 text-emerald-100 font-bold shadow-xs";
                        }

                        return (
                          <td key={idx} className="p-1 text-center">
                            <div
                              data-testid={`heatmap-cell-${day}-${TIME_BLOCKS[idx].id}`}
                              title={`${day} ${TIME_BLOCKS[idx].label} (${TIME_BLOCKS[idx].hours}): ${rate} response rate`}
                              className={`mx-auto flex h-8 w-full max-w-[80px] items-center justify-center rounded border transition-all hover:scale-105 hover:ring-1 hover:ring-emerald-400 ${cellStyle}`}
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
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 pt-3 text-[10px] text-zinc-400">
            <span className="font-mono text-zinc-500">Engagement Intensity:</span>
            <div className="flex items-center gap-3 font-mono">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-zinc-800 bg-zinc-900/40" />
                <span>Off-Peak (&lt;25%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-500/20 bg-emerald-500/10" />
                <span>Moderate (25-50%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-500/40 bg-emerald-500/25" />
                <span>High Signal (50-75%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded border border-emerald-400/60 bg-emerald-500/45" />
                <span className="text-emerald-300">Peak Resonance (&gt;75%)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Topic Pillar Distribution (5 cols) */}
        <div
          data-testid="topic-pillar-breakdown"
          className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 lg:col-span-5"
        >
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2">
              <TrendUp size={16} className="text-emerald-400" />
              <h2 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
                Topic Pillar Distribution
              </h2>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">
              4 Focus Areas
            </span>
          </div>

          <p className="mt-2 text-xs text-zinc-400">
            Performance breakdown across target technological focus areas.
          </p>

          <div className="mt-4 space-y-4">
            {TOPIC_PILLARS.map((pillar) => (
              <div
                key={pillar.name}
                data-testid={`topic-pillar-${pillar.name}`}
                className="rounded-md border border-zinc-800/80 bg-zinc-950/50 p-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-semibold text-zinc-200">
                      {pillar.name}
                    </h3>
                    <span className="font-mono text-[10px] text-zinc-500">
                      {pillar.tag}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-xs font-bold text-emerald-400">
                      {pillar.replyRate}
                    </span>
                    <p className="font-mono text-[10px] text-zinc-500">
                      reply rate
                    </p>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full bg-emerald-400 transition-all duration-300"
                    style={{ width: `${pillar.percentage}%` }}
                  />
                </div>

                <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-zinc-400">
                  <span>{pillar.commentsCount} comments engaged</span>
                  <span>{pillar.impressions} impressions</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Section: Recent High-Impact Comments Table */}
      <div
        data-testid="high-impact-comments-table"
        className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
      >
        <div className="flex flex-col justify-between gap-1 border-b border-zinc-800/80 pb-3 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <ChatTeardropDots size={16} className="text-emerald-400" />
            <h2 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
              Recent High-Impact Comments
            </h2>
          </div>
          <span className="font-mono text-[10px] text-zinc-500">
            Top performing executed comments with author responses
          </span>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-[11px] font-mono text-zinc-500">
                <th className="pb-2.5 font-medium">Target Author</th>
                <th className="pb-2.5 font-medium">Topic Tag</th>
                <th className="pb-2.5 font-medium">Comment Excerpt</th>
                <th className="pb-2.5 font-medium">Response Status</th>
                <th className="pb-2.5 font-medium">Reach</th>
                <th className="pb-2.5 font-medium text-right">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {displayComments.map((comment) => (
                <tr
                  key={comment.id}
                  data-testid={`comment-row-${comment.id}`}
                  className="hover:bg-zinc-800/30"
                >
                  <td className="py-3 pr-3">
                    <div className="font-semibold text-zinc-200">
                      {comment.author}
                    </div>
                    <div className="text-[11px] text-zinc-500 line-clamp-1">
                      {comment.headline}
                    </div>
                  </td>
                  <td className="py-3 pr-3 whitespace-nowrap">
                    <span className="rounded border border-zinc-700/60 bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                      {comment.topic}
                    </span>
                  </td>
                  <td className="py-3 pr-3 max-w-xs">
                    <p className="line-clamp-2 text-zinc-400 leading-relaxed italic">
                      "{comment.commentExcerpt}"
                    </p>
                  </td>
                  <td className="py-3 pr-3 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-400">
                      <CheckCircle size={12} weight="bold" />
                      Author Replied
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-mono text-zinc-300 whitespace-nowrap">
                    {comment.reach}
                  </td>
                  <td className="py-3 font-mono text-[11px] text-zinc-500 text-right whitespace-nowrap">
                    {comment.timestamp}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
