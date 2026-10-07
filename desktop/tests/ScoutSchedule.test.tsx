import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ScoutScheduleCard } from "../src/components/calendar/ScoutScheduleCard";
import { ScoutScheduleModal } from "../src/components/calendar/ScoutScheduleModal";
import { AppProvider } from "../src/context/AppContext";
import { AutomatedCommentWindow } from "../src/types";

const mockWindows: AutomatedCommentWindow[] = [
  {
    id: "win-1",
    title: "Morning Feed Scout Window",
    start_time: "08:00",
    end_time: "09:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Engineering Leadership",
  },
  {
    id: "win-2",
    title: "Midday Feed Scout Window",
    start_time: "13:00",
    end_time: "14:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "paused",
    topic_filter: "Distributed Systems",
  },
];

describe("Scout Schedule UI Components", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    (window as any).api = {
      fetchState: vi.fn().mockResolvedValue({
        pending_actions: [],
        daily_counters: { comments_executed: 0, posts_executed: 0, suggestions_sent: 0, connections_sent: 0 },
        history: [],
        paused: false,
      }),
      fetchScoutSchedule: vi.fn().mockResolvedValue(mockWindows),
      saveScoutSchedule: vi.fn().mockResolvedValue(true),
      getSettings: vi.fn().mockResolvedValue({ timezone: "UTC" }),
      onRealtimeEvent: vi.fn().mockReturnValue(() => {}),
    };
  });

  describe("ScoutScheduleCard", () => {
    it("renders windows with titles and status indicators", async () => {
      render(
        <AppProvider>
          <ScoutScheduleCard commentWindows={mockWindows} />
        </AppProvider>
      );

      await waitFor(() => {
        expect(screen.getByText("Morning Feed Scout Window")).toBeTruthy();
      });
      expect(screen.getByText("Midday Feed Scout Window")).toBeTruthy();
      expect(screen.getByText("Paused")).toBeTruthy();
      expect(screen.getByTestId("edit-scout-schedule-btn")).toBeTruthy();
    });

    it("clicking toggle updates window status and persists via saveScoutSchedule", async () => {
      const saveMock = vi.fn().mockResolvedValue(true);
      (window as any).api.saveScoutSchedule = saveMock;

      render(
        <AppProvider>
          <ScoutScheduleCard commentWindows={mockWindows} />
        </AppProvider>
      );

      const toggleButtons = await screen.findAllByRole("button", { name: /toggle scout window/i });
      expect(toggleButtons.length).toBe(2);

      // Toggle first window
      fireEvent.click(toggleButtons[0]);

      await waitFor(() => {
        expect(saveMock).toHaveBeenCalled();
      });
    });

    it("opens ScoutScheduleModal when clicking Configure Schedule", async () => {
      render(
        <AppProvider>
          <ScoutScheduleCard commentWindows={mockWindows} />
        </AppProvider>
      );

      const configBtn = await screen.findByTestId("edit-scout-schedule-btn");
      fireEvent.click(configBtn);

      expect(screen.getByText("Configure Automated Scout Runs")).toBeTruthy();
    });
  });

  describe("ScoutScheduleModal", () => {
    it("allows adding a new window and saving", async () => {
      const handleSave = vi.fn().mockResolvedValue(true);
      const handleClose = vi.fn();

      render(
        <ScoutScheduleModal
          isOpen={true}
          onClose={handleClose}
          commentWindows={mockWindows}
          onSave={handleSave}
          timezone="UTC"
        />
      );

      // Check initial 2 windows rendered
      expect(screen.getByDisplayValue("Morning Feed Scout Window")).toBeTruthy();
      expect(screen.getByDisplayValue("Midday Feed Scout Window")).toBeTruthy();

      // Click Add Another Scout Window
      const addBtn = screen.getByText("Add Another Scout Window");
      fireEvent.click(addBtn);

      expect(screen.getByDisplayValue("Scout Window 3")).toBeTruthy();

      // Click Save & Sync Schedule
      const saveBtn = screen.getByText("Save & Sync Schedule");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(handleSave).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({ title: "Scout Window 3" }),
          ])
        );
        expect(handleClose).toHaveBeenCalled();
      });
    });

    it("allows removing a window", async () => {
      const handleSave = vi.fn().mockResolvedValue(true);
      const handleClose = vi.fn();

      render(
        <ScoutScheduleModal
          isOpen={true}
          onClose={handleClose}
          commentWindows={mockWindows}
          onSave={handleSave}
          timezone="UTC"
        />
      );

      const deleteButtons = screen.getAllByTitle("Remove this scout window");
      expect(deleteButtons.length).toBe(2);

      // Remove second window
      fireEvent.click(deleteButtons[1]);

      // Only first window remains
      expect(screen.getByDisplayValue("Morning Feed Scout Window")).toBeTruthy();
      expect(screen.queryByDisplayValue("Midday Feed Scout Window")).toBeNull();
    });
  });
});
