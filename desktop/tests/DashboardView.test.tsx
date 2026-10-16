import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { DashboardView } from "../src/views/DashboardView";

describe("DashboardView", () => {
  const renderDashboard = () => {
    return render(
      <AppProvider>
        <DashboardView />
      </AppProvider>
    );
  };

  it("renders Command Center header", () => {
    renderDashboard();
    expect(screen.getByText("Command Center")).toBeTruthy();
    expect(screen.queryByTestId("status-pill")).toBeNull();
  });

  it("renders telemetry status metrics", () => {
    renderDashboard();
    expect(screen.getByText("NVIDIA NIM Model")).toBeTruthy();
    expect(screen.getByText("No Active Session")).toBeTruthy();
    expect(screen.getByText("Not configured")).toBeTruthy();
  });

  it("renders all three daily quota burn-down cards", () => {
    renderDashboard();
    const quotaCards = screen.getAllByTestId("quota-card");
    expect(quotaCards.length).toBe(3);

    expect(screen.getByText("Comments Executed")).toBeTruthy();
    expect(screen.getByText("Posts Published")).toBeTruthy();
    expect(screen.getByText("Suggestions Reviewed")).toBeTruthy();

    const progressBars = screen.getAllByRole("progressbar");
    expect(progressBars.length).toBe(3);
  });

  it("handles trigger scout button click", async () => {
    renderDashboard();
    const scoutBtn = screen.getByTestId("trigger-scout-btn");
    expect(scoutBtn.textContent).toContain("Trigger Scout Now");

    fireEvent.click(scoutBtn);
    expect(screen.getByTestId("trigger-feedback")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByTestId("trigger-feedback").textContent).toContain("Scout");
    });
  });

  it("does not render duplicate pause agent button, health check button, or edge cycle badge", () => {
    renderDashboard();
    expect(screen.queryByTestId("toggle-pause-btn")).toBeNull();
    expect(screen.queryByTestId("health-check-btn")).toBeNull();
    expect(screen.queryByText(/Edge Cycle/i)).toBeNull();
  });

  it("renders pending approval queue preview card", () => {
    renderDashboard();
    expect(screen.getByText("Pending Approval Queue")).toBeTruthy();
    expect(screen.getByText("Review Queue")).toBeTruthy();
  });

  it("renders standard empty queue preview when pendingCount is 0", () => {
    // If pending count is 0, should display standard empty queue
    render(
      <AppProvider>
        <DashboardView />
      </AppProvider>
    );
    expect(screen.getByText("Pending Approval Queue")).toBeTruthy();
  });
});
