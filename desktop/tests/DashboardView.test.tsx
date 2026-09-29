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

  it("renders Command Center header and status indicator", () => {
    renderDashboard();
    expect(screen.getByText("Command Center")).toBeTruthy();
    expect(screen.getByTestId("status-pill")).toBeTruthy();
  });

  it("renders telemetry status metrics", () => {
    renderDashboard();
    expect(screen.getByText("State Persistence")).toBeTruthy();
    expect(screen.getByText("Cloudflare KV")).toBeTruthy();
    expect(screen.getByText("NVIDIA NIM Model")).toBeTruthy();
    expect(screen.getByText("Active & Encrypted")).toBeTruthy();
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

  it("handles toggle pause action", () => {
    renderDashboard();
    const pauseBtn = screen.getByTestId("toggle-pause-btn");
    expect(pauseBtn.textContent).toContain("Pause Agent");

    fireEvent.click(pauseBtn);
    expect(screen.getByTestId("toggle-pause-btn").textContent).toContain("Resume Agent");
  });

  it("renders pending approval queue preview card", () => {
    renderDashboard();
    expect(screen.getByText("Pending Approval Queue")).toBeTruthy();
    expect(screen.getByText("Review Queue")).toBeTruthy();
  });
});
