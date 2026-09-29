import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { CalendarView } from "../src/views/CalendarView";

describe("CalendarView", () => {
  const renderCalendar = () => {
    return render(
      <AppProvider>
        <CalendarView />
      </AppProvider>
    );
  };

  it("renders Content Calendar header and interval controls", () => {
    renderCalendar();
    expect(screen.getByText("Content Calendar & Planner")).toBeTruthy();
    expect(screen.getByTestId("cal-prev-btn")).toBeTruthy();
    expect(screen.getByTestId("cal-next-btn")).toBeTruthy();
    expect(screen.getByTestId("cal-today-btn")).toBeTruthy();
    expect(screen.getByTestId("cal-range-label")).toBeTruthy();
    expect(screen.getByTestId("new-post-btn")).toBeTruthy();
  });

  it("renders week view grid with scheduled original posts and automated comment windows", () => {
    renderCalendar();
    expect(screen.getByTestId("calendar-week-grid")).toBeTruthy();

    // Check automated comment windows rendered in calendar
    const commentWindows = screen.getAllByTestId("calendar-comment-window");
    expect(commentWindows.length).toBeGreaterThan(0);
    expect(screen.getAllByText("Morning Feed Scout").length).toBeGreaterThan(0);

    // Check scheduled original posts rendered in calendar
    const postCards = screen.getAllByTestId("calendar-post-card");
    expect(postCards.length).toBeGreaterThan(0);
    expect(
      screen.getByText("The 3 Invariants of Production LLM Agents")
    ).toBeTruthy();
  });

  it("displays post status badges for Draft, Scheduled, and Published", () => {
    renderCalendar();

    // We have initial scheduled posts with status "scheduled" and "published"
    const scheduledBadges = screen.getAllByTestId("status-badge-scheduled");
    expect(scheduledBadges.length).toBeGreaterThan(0);

    const publishedBadges = screen.getAllByTestId("status-badge-published");
    expect(publishedBadges.length).toBeGreaterThan(0);
  });

  it("toggles between Week View and Month View", () => {
    renderCalendar();
    const weekBtn = screen.getByTestId("view-mode-week");
    const monthBtn = screen.getByTestId("view-mode-month");

    // Initially week grid is visible
    expect(screen.getByTestId("calendar-week-grid")).toBeTruthy();
    expect(screen.queryByTestId("calendar-month-grid")).toBeNull();

    // Switch to month view
    fireEvent.click(monthBtn);
    expect(screen.queryByTestId("calendar-week-grid")).toBeNull();
    expect(screen.getByTestId("calendar-month-grid")).toBeTruthy();

    // Switch back to week view
    fireEvent.click(weekBtn);
    expect(screen.getByTestId("calendar-week-grid")).toBeTruthy();
  });

  it("filters scheduled posts by status filter pills", () => {
    renderCalendar();
    const filterScheduled = screen.getByTestId("filter-scheduled");
    const filterDraft = screen.getByTestId("filter-draft");
    const filterAll = screen.getByTestId("filter-all");

    // Filter to Drafts
    fireEvent.click(filterDraft);
    // Post-001 (scheduled) should not be visible now
    expect(screen.queryByText("The 3 Invariants of Production LLM Agents")).toBeNull();

    // Filter back to All
    fireEvent.click(filterAll);
    expect(screen.getByText("The 3 Invariants of Production LLM Agents")).toBeTruthy();

    // Filter to Scheduled
    fireEvent.click(filterScheduled);
    expect(screen.getByText("The 3 Invariants of Production LLM Agents")).toBeTruthy();
  });

  it("opens post detail modal when a post card is clicked", () => {
    renderCalendar();
    const postTitle = screen.getByText("The 3 Invariants of Production LLM Agents");
    fireEvent.click(postTitle);

    // Modal opens
    const modal = screen.getByTestId("post-detail-modal");
    expect(modal).toBeTruthy();
    expect(modal.textContent).toContain("Deterministic State Storage");
    expect(modal.textContent).toContain("hitl-agent-architecture.pdf");
    expect(screen.getByTestId("edit-in-composer-btn")).toBeTruthy();

    // Close modal
    const closeBtn = screen.getByTestId("close-modal-btn");
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId("post-detail-modal")).toBeNull();
  });

  it("navigates time intervals using prev and next buttons", () => {
    renderCalendar();
    const rangeLabel = screen.getByTestId("cal-range-label");
    const initialText = rangeLabel.textContent;

    const nextBtn = screen.getByTestId("cal-next-btn");
    fireEvent.click(nextBtn);
    expect(rangeLabel.textContent).not.toBe(initialText);

    const prevBtn = screen.getByTestId("cal-prev-btn");
    fireEvent.click(prevBtn);
    expect(rangeLabel.textContent).toBe(initialText);
  });
});
