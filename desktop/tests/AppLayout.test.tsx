import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { AppLayout } from "../src/layouts/AppLayout";

describe("AppLayout", () => {
  const renderLayout = () => {
    return render(
      <AppProvider>
        <AppLayout>
          <div data-testid="test-content">Main Content Area</div>
        </AppLayout>
      </AppProvider>
    );
  };

  it("renders the brand header and main content area", () => {
    renderLayout();
    expect(screen.getByText("HITL Cockpit")).toBeTruthy();
    expect(screen.getByTestId("test-content")).toBeTruthy();
  });

  it("renders all navigation tabs in the sidebar", () => {
    renderLayout();
    expect(screen.getByTestId("nav-dashboard")).toBeTruthy();
    expect(screen.getByTestId("nav-queue")).toBeTruthy();
    expect(screen.getByTestId("nav-vault")).toBeTruthy();
    expect(screen.getByTestId("nav-history")).toBeTruthy();
    expect(screen.getByTestId("nav-doctor")).toBeTruthy();
    expect(screen.getByTestId("nav-settings")).toBeTruthy();
  });

  it("renders top bar with worker URL, pending badge, and status pill", () => {
    renderLayout();
    expect(screen.getByText(/relay\.hitl-agent\.workers\.dev/i)).toBeTruthy();
    expect(screen.getByTestId("pending-badge-button")).toBeTruthy();
    expect(screen.getByText("3 Pending")).toBeTruthy();
    expect(screen.getByTestId("status-pill")).toBeTruthy();
  });

  it("collapses and expands the sidebar when toggle button is clicked", () => {
    renderLayout();
    const sidebar = screen.getByTestId("sidebar");
    const toggleBtn = screen.getByTestId("collapse-toggle");

    // Initially expanded (w-60)
    expect(sidebar.className).toContain("w-60");

    // Click to collapse
    fireEvent.click(toggleBtn);
    expect(sidebar.className).toContain("w-16");

    // Click to expand again
    fireEvent.click(toggleBtn);
    expect(sidebar.className).toContain("w-60");
  });

  it("toggles pause agent state from the top bar button", () => {
    renderLayout();
    const pauseBtn = screen.getByTestId("global-pause-button");
    expect(pauseBtn.textContent).toContain("Pause Agent");

    // Click to pause
    fireEvent.click(pauseBtn);
    expect(screen.getByTestId("global-pause-button").textContent).toContain("Resume Agent");

    // Click to resume
    fireEvent.click(screen.getByTestId("global-pause-button"));
    expect(screen.getByTestId("global-pause-button").textContent).toContain("Pause Agent");
  });

  it("allows switching navigation tabs", () => {
    renderLayout();
    const queueNav = screen.getByTestId("nav-queue");
    fireEvent.click(queueNav);
    expect(queueNav.className).toContain("bg-zinc-800/90");
  });
});
