import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import {
  AnalyticsView,
  DEFAULT_HEATMAP_DATA,
  DEFAULT_HEATMAP_RATES,
} from "../src/views/AnalyticsView";

const mockTopicPillars = [
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

const mockComments = [
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
];

describe("AnalyticsView", () => {
  it("renders the view header and live analytics title", () => {
    render(
      <AppProvider>
        <AnalyticsView />
      </AppProvider>
    );
    expect(screen.getByText("LinkedIn Growth Analytics")).toBeTruthy();
    expect(screen.getByText("Live Analytics")).toBeTruthy();
    expect(
      screen.getByText(/Real-time engagement telemetry/i)
    ).toBeTruthy();
  });

  it("renders standard empty states when no audit or engagement data is available", () => {
    render(
      <AppProvider>
        <AnalyticsView />
      </AppProvider>
    );

    // KPI 1: Executed Actions -> empty indicator
    const reachCard = screen.getByTestId("kpi-reach");
    expect(reachCard.textContent).toContain("Executed Actions");
    expect(reachCard.textContent).toContain("--");

    // KPI 2: Approval Rate -> 0%
    const replyCard = screen.getByTestId("kpi-reply-rate");
    expect(replyCard.textContent).toContain("Approval Rate");
    expect(replyCard.textContent).toContain("0%");

    // KPI 3: Approval Velocity -> empty indicator
    const velocityCard = screen.getByTestId("kpi-velocity");
    expect(velocityCard.textContent).toContain("Approval Velocity");
    expect(velocityCard.textContent).toContain("--");

    // KPI 4: Active Focus Areas -> empty indicator
    const scoreCard = screen.getByTestId("kpi-engagement-score");
    expect(scoreCard.textContent).toContain("Active Focus Areas");
    expect(scoreCard.textContent).toContain("--");

    // Empty state for heatmap
    expect(screen.getByTestId("heatmap-empty")).toBeTruthy();
    expect(screen.getByText("No engagement data recorded yet.")).toBeTruthy();

    // Empty state for topic pillars
    expect(screen.getByTestId("topic-pillar-empty")).toBeTruthy();
    expect(
      screen.getByText("No topic metrics recorded yet. Metrics will appear once comments are executed.")
    ).toBeTruthy();

    // Empty state table row for comments
    expect(
      screen.getByText(
        /No high-impact comments recorded yet. Comments will appear here once executed and engagement is tracked./i
      )
    ).toBeTruthy();
  });

  it("renders populated heatmap, topic pillars, and comments when provided via fixtures", () => {
    render(
      <AppProvider>
        <AnalyticsView
          initialComments={mockComments}
          initialTopicPillars={mockTopicPillars}
          initialHeatmapData={DEFAULT_HEATMAP_DATA}
          initialHeatmapRates={DEFAULT_HEATMAP_RATES}
        />
      </AppProvider>
    );

    // Check heatmap matrix
    expect(screen.getByTestId("heatmap-matrix")).toBeTruthy();
    expect(screen.getByText("Weekly Time-of-Day Engagement Matrix")).toBeTruthy();
    expect(screen.getByTestId("heatmap-cell-Thu-midday")).toBeTruthy();
    expect(screen.getByTestId("heatmap-cell-Mon-morning")).toBeTruthy();

    // Check topic pillars
    expect(screen.getByTestId("topic-pillar-breakdown")).toBeTruthy();
    expect(screen.getByTestId("topic-pillar-Distributed Systems")).toBeTruthy();
    expect(screen.getByTestId("topic-pillar-Enterprise AI")).toBeTruthy();
    expect(screen.getByText("39.5%")).toBeTruthy();

    // Check high-impact comments
    expect(screen.getByTestId("high-impact-comments-table")).toBeTruthy();
    expect(screen.getByText("Satya Nadella")).toBeTruthy();
    expect(screen.getByText("Kelsey Hightower")).toBeTruthy();
  });

  it("allows switching timeframe filters and triggering metric refresh", async () => {
    render(
      <AppProvider>
        <AnalyticsView />
      </AppProvider>
    );

    const sevenDaysBtn = screen.getByRole("button", { name: "7 Days" });
    const thirtyDaysBtn = screen.getByRole("button", { name: "30 Days" });
    const allTimeBtn = screen.getByRole("button", { name: "All Time" });

    expect(sevenDaysBtn).toBeTruthy();
    expect(thirtyDaysBtn).toBeTruthy();
    expect(allTimeBtn).toBeTruthy();

    // Click 30 Days
    fireEvent.click(thirtyDaysBtn);
    expect(thirtyDaysBtn.className).toContain("bg-zinc-800");

    // Click All Time
    fireEvent.click(allTimeBtn);
    expect(allTimeBtn.className).toContain("bg-zinc-800");

    // Click Refresh
    const refreshBtn = screen.getByTestId("refresh-analytics-btn");
    await act(async () => {
      fireEvent.click(refreshBtn);
    });
  });

  it("dynamically calculates heatmap, topic pillars, and KPIs from auditEntries", () => {
    const executedAudit: any[] = [
      {
        id: "audit-1",
        itemId: "item-1",
        actionType: "comment",
        status: "executed_success",
        decidedAt: "2026-09-29T10:00:00Z",
        executedAt: "2026-09-29T10:00:15Z",
        targetAuthor: "Guido van Rossum",
        targetHeadline: "Distinguished Engineer at Microsoft",
        draftExcerpt: "Distributed state machines and Python async architecture insights.",
      },
      {
        id: "audit-2",
        itemId: "item-2",
        actionType: "comment",
        status: "executed_success",
        decidedAt: "2026-09-29T14:30:00Z",
        executedAt: "2026-09-29T14:30:45Z",
        targetAuthor: "Demis Hassabis",
        targetHeadline: "CEO at Google DeepMind",
        draftExcerpt: "Enterprise AI and reasoning models need strict deterministic verification.",
      },
    ];

    render(
      <AppProvider>
        <AnalyticsView initialAuditEntries={executedAudit} />
      </AppProvider>
    );

    // Heatmap should NOT be empty; should render the matrix
    expect(screen.queryByTestId("heatmap-empty")).toBeNull();
    expect(screen.getByTestId("heatmap-matrix")).toBeTruthy();

    // Topic pillars should NOT be empty
    expect(screen.queryByTestId("topic-pillar-empty")).toBeNull();
    expect(screen.getByTestId("topic-pillar-breakdown")).toBeTruthy();

    // High impact comments should show the executed authors
    expect(screen.getByText("Guido van Rossum")).toBeTruthy();
    expect(screen.getByText("Demis Hassabis")).toBeTruthy();

    // KPIs should not be empty dashes
    const reachCard = screen.getByTestId("kpi-reach");
    expect(reachCard.textContent).not.toContain("--");

    const replyCard = screen.getByTestId("kpi-reply-rate");
    expect(replyCard.textContent).toContain("100%");

    const velocityCard = screen.getByTestId("kpi-velocity");
    expect(velocityCard.textContent).toContain("30s");
  });
});
