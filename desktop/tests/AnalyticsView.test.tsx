import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { AnalyticsView } from "../src/views/AnalyticsView";

describe("AnalyticsView", () => {
  const renderAnalytics = () => {
    return render(
      <AppProvider>
        <AnalyticsView />
      </AppProvider>
    );
  };

  it("renders the view header and cockpit title", () => {
    renderAnalytics();
    expect(screen.getByText("LinkedIn Growth Analytics")).toBeTruthy();
    expect(screen.getByText("Live Cockpit")).toBeTruthy();
    expect(
      screen.getByText(/Real-time engagement telemetry, author reply conversions/i)
    ).toBeTruthy();
  });

  it("renders all top metrics row KPI cards with high-signal data", () => {
    renderAnalytics();

    // KPI 1: Estimated Reach / Impressions
    const reachCard = screen.getByTestId("kpi-reach");
    expect(reachCard).toBeTruthy();
    expect(reachCard.textContent).toContain("Estimated Reach / Impressions");
    expect(reachCard.textContent).toContain("48.2k");
    expect(reachCard.textContent).toContain("+14.2%");

    // KPI 2: Author Reply Conversion Rate
    const replyCard = screen.getByTestId("kpi-reply-rate");
    expect(replyCard).toBeTruthy();
    expect(replyCard.textContent).toContain("Author Reply Conversion Rate");
    expect(replyCard.textContent).toContain("34.8%");

    // KPI 3: Approval Velocity
    const velocityCard = screen.getByTestId("kpi-velocity");
    expect(velocityCard).toBeTruthy();
    expect(velocityCard.textContent).toContain("Approval Velocity");
    expect(velocityCard.textContent).toContain("42s");

    // KPI 4: Topic Engagement Score
    const scoreCard = screen.getByTestId("kpi-engagement-score");
    expect(scoreCard).toBeTruthy();
    expect(scoreCard.textContent).toContain("Topic Engagement Score");
    expect(scoreCard.textContent).toContain("94/100");
  });

  it("renders the 7x4 Weekly Time-of-Day Engagement Matrix heatmap", () => {
    renderAnalytics();

    const heatmap = screen.getByTestId("heatmap-matrix");
    expect(heatmap).toBeTruthy();
    expect(
      screen.getByText("Weekly Time-of-Day Engagement Matrix")
    ).toBeTruthy();

    // Check Days
    for (const day of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
      expect(screen.getByText(day)).toBeTruthy();
    }

    // Check Time Block columns
    expect(screen.getByText("Morning")).toBeTruthy();
    expect(screen.getByText("Midday")).toBeTruthy();
    expect(screen.getByText("Afternoon")).toBeTruthy();
    expect(screen.getByText("Evening")).toBeTruthy();

    // Check specific heatmap cells
    expect(screen.getByTestId("heatmap-cell-Thu-midday")).toBeTruthy();
    expect(screen.getByTestId("heatmap-cell-Mon-morning")).toBeTruthy();
  });

  it("renders the Topic Pillar Distribution across all core focus areas", () => {
    renderAnalytics();

    const breakdown = screen.getByTestId("topic-pillar-breakdown");
    expect(breakdown).toBeTruthy();
    expect(screen.getByText("Topic Pillar Distribution")).toBeTruthy();

    // 4 focus areas
    expect(
      screen.getByTestId("topic-pillar-Distributed Systems")
    ).toBeTruthy();
    expect(screen.getByTestId("topic-pillar-Enterprise AI")).toBeTruthy();
    expect(
      screen.getByTestId("topic-pillar-Browser Automation")
    ).toBeTruthy();
    expect(screen.getByTestId("topic-pillar-Cloudflare Edge")).toBeTruthy();

    // Verify reply rates
    expect(screen.getByText("39.5%")).toBeTruthy();
    expect(screen.getByText("36.8%")).toBeTruthy();
    expect(screen.getByText("32.1%")).toBeTruthy();
    expect(screen.getByText("28.4%")).toBeTruthy();
  });

  it("renders the Recent High-Impact Comments table with verified authors and metrics", () => {
    renderAnalytics();

    const table = screen.getByTestId("high-impact-comments-table");
    expect(table).toBeTruthy();
    expect(screen.getByText("Recent High-Impact Comments")).toBeTruthy();

    // Verify top authors
    expect(screen.getByText("Satya Nadella")).toBeTruthy();
    expect(screen.getByText("Kelsey Hightower")).toBeTruthy();
    expect(screen.getByText("Andrej Karpathy")).toBeTruthy();
    expect(screen.getByText("Mitchell Hashimoto")).toBeTruthy();

    // Verify response badges
    const badges = screen.getAllByText("Author Replied");
    expect(badges.length).toBeGreaterThanOrEqual(4);
  });

  it("allows switching timeframe filters and triggering metric refresh", () => {
    renderAnalytics();

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
    fireEvent.click(refreshBtn);
  });
});
