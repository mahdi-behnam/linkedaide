import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { ThemeProvider } from "../src/context/ThemeContext";
import { AppLayout } from "../src/layouts/AppLayout";

describe("AppLayout", () => {
  const renderLayout = () => {
    return render(
      <ThemeProvider>
        <AppProvider>
          <AppLayout>
            <div data-testid="test-content">Main Content Area</div>
          </AppLayout>
        </AppProvider>
      </ThemeProvider>
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
    expect(screen.getByTestId("nav-outreach")).toBeTruthy();
    expect(screen.getByTestId("nav-composer")).toBeTruthy();
    expect(screen.getByTestId("nav-calendar")).toBeTruthy();
    expect(screen.getByTestId("nav-analytics")).toBeTruthy();
    expect(screen.getByTestId("nav-vault")).toBeTruthy();
    expect(screen.getByTestId("nav-history")).toBeTruthy();
    expect(screen.getByTestId("nav-doctor")).toBeTruthy();
    expect(screen.getByTestId("nav-settings")).toBeTruthy();
  });

  it("renders top bar with worker URL, pending badge, and status pill", () => {
    renderLayout();
    expect(screen.getByText(/relay\.hitl-agent\.workers\.dev/i)).toBeTruthy();
    expect(screen.getByTestId("pending-badge-button")).toBeTruthy();
    expect(screen.getByText("0 Pending")).toBeTruthy();
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
    expect(queueNav.className).toContain("bg-surface-container-highest");
  });

  it("navigates through tab history with back and forward buttons", () => {
    renderLayout();
    const backBtn = screen.getByTestId("nav-back-btn");
    const forwardBtn = screen.getByTestId("nav-forward-btn");

    // Initially at dashboard, back should be disabled
    expect(backBtn.getAttribute("disabled")).not.toBeNull();
    expect(forwardBtn.getAttribute("disabled")).not.toBeNull();

    // Navigate to Approval Queue
    fireEvent.click(screen.getByTestId("nav-queue"));
    expect(screen.getByTestId("nav-queue").className).toContain("bg-surface-container-highest");
    expect(backBtn.getAttribute("disabled")).toBeNull();
    expect(forwardBtn.getAttribute("disabled")).not.toBeNull();

    // Navigate to Diagnostics
    fireEvent.click(screen.getByTestId("nav-doctor"));
    expect(screen.getByTestId("nav-doctor").className).toContain("bg-surface-container-highest");

    // Click Back to go to Queue
    fireEvent.click(backBtn);
    expect(screen.getByTestId("nav-queue").className).toContain("bg-surface-container-highest");
    expect(forwardBtn.getAttribute("disabled")).toBeNull();

    // Click Back to go to Dashboard
    fireEvent.click(backBtn);
    expect(screen.getByTestId("nav-dashboard").className).toContain("bg-surface-container-highest");
    expect(backBtn.getAttribute("disabled")).not.toBeNull();

    // Click Forward to return to Queue
    fireEvent.click(forwardBtn);
    expect(screen.getByTestId("nav-queue").className).toContain("bg-surface-container-highest");
  });

  it("opens command palette via search bar trigger, filters items, and navigates", () => {
    renderLayout();
    const searchTrigger = screen.getByTestId("search-bar-trigger");
    expect(screen.queryByTestId("command-palette")).toBeNull();

    // Open palette
    fireEvent.click(searchTrigger);
    expect(screen.getByTestId("command-palette")).toBeTruthy();

    // Filter items
    const input = screen.getByTestId("command-palette-input");
    fireEvent.change(input, { target: { value: "Composer" } });
    expect(screen.getByText("Post Composer Studio")).toBeTruthy();
    expect(screen.queryByText("System Diagnostics")).toBeNull();

    // Select item to navigate and close palette
    fireEvent.click(screen.getByTestId("palette-item-tab-composer"));
    expect(screen.queryByTestId("command-palette")).toBeNull();
    expect(screen.getByTestId("nav-composer").className).toContain("bg-surface-container-highest");
  });

  it("opens command palette via ⌘K shortcut and closes on Escape", () => {
    renderLayout();
    expect(screen.queryByTestId("command-palette")).toBeNull();

    // Press Cmd+K
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByTestId("command-palette")).toBeTruthy();

    // Press Escape
    fireEvent.keyDown(screen.getByTestId("command-palette-input"), { key: "Escape" });
    expect(screen.queryByTestId("command-palette")).toBeNull();
  });
});

