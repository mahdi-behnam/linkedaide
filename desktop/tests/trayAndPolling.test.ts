import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Menu } from "electron";
import { TrayManager, FALLBACK_TRAY_ICON_DATA_URL } from "../electron/tray/trayManager";
import { PollingEngine } from "../electron/tray/pollingEngine";
import { WorkerClient } from "../electron/api/workerClient";
import type { AgentState } from "../electron/types";

const mocks = vi.hoisted(() => {
  class MockTray {
    setToolTip = vi.fn();
    setTitle = vi.fn();
    setContextMenu = vi.fn();
    on = vi.fn();
    destroy = vi.fn();
    isDestroyed = vi.fn().mockReturnValue(false);
  }

  class MockNotification {
    title: string;
    body: string;
    show = vi.fn();
    on = vi.fn();

    constructor(options?: { title?: string; body?: string }) {
      this.title = options?.title || "";
      this.body = options?.body || "";
      mocks.activeNotification = this;
      mocks.notifications.push(this);
    }
  }

  const mockWebContents = {
    send: vi.fn(),
    isDestroyed: vi.fn().mockReturnValue(false),
  };

  const mockBrowserWindow = {
    show: vi.fn(),
    focus: vi.fn(),
    restore: vi.fn(),
    isMinimized: vi.fn().mockReturnValue(false),
    webContents: mockWebContents,
  };

  return {
    MockTray,
    MockNotification,
    activeTray: null as any,
    activeNotification: null as any,
    notifications: [] as any[],
    mockBrowserWindow,
    mockWebContents,
  };
});

vi.mock("electron", () => {
  return {
    app: {
      quit: vi.fn(),
      isQuitting: false,
    },
    Tray: class extends mocks.MockTray {
      constructor() {
        super();
        mocks.activeTray = this;
      }
    },
    Menu: {
      buildFromTemplate: vi.fn((template) => ({ items: template })),
    },
    Notification: mocks.MockNotification,
    nativeImage: {
      createFromDataURL: vi.fn((dataUrl: string) => ({
        toDataURL: () => dataUrl,
        isEmpty: () => false,
      })),
    },
    BrowserWindow: vi.fn().mockImplementation(() => mocks.mockBrowserWindow),
    ipcMain: {
      emit: vi.fn(),
      on: vi.fn(),
    },
  };
});

describe("System Tray & Notification Engine", () => {
  let mockWorkerClient: WorkerClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.activeTray = null;
    mocks.activeNotification = null;
    mocks.notifications.length = 0;
    mockWorkerClient = new WorkerClient({
      baseUrl: "https://worker.example.workers.dev",
      apiSecret: "secret-key",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("TrayManager", () => {
    it("creates an Electron Tray instance with fallback icon", () => {
      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );

      expect(mocks.activeTray).not.toBeNull();
      expect(trayManager.getTray()).toBe(mocks.activeTray);
      expect(mocks.activeTray!.setToolTip).toHaveBeenCalledWith(
        "LinkedIn HITL Agent"
      );
      expect(mocks.activeTray!.setContextMenu).toHaveBeenCalled();
      expect(trayManager.getMainWindow()).toBe(mocks.mockBrowserWindow);
      expect(FALLBACK_TRAY_ICON_DATA_URL).toMatch(/^data:image\/png;base64,/);
    });

    it("builds context menu with required actions", () => {
      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );
      const template = trayManager.getContextMenuTemplate();

      // Verify all required menu item labels
      const labels = template.map((item) => item.label).filter(Boolean);
      expect(labels).toContain("Open Dashboard");
      expect(labels).toContain("Trigger Scout Now");
      expect(labels).toContain("Pause / Resume Agent");
      expect(labels).toContain("Reset Circuit Breaker");
      expect(labels).toContain("Quit");

      // Verify separator exists
      const hasSeparator = template.some((item) => item.type === "separator");
      expect(hasSeparator).toBe(true);

      // Verify Menu.buildFromTemplate was invoked with required items
      expect(Menu.buildFromTemplate).toHaveBeenCalled();
      const calledTemplate = vi.mocked(Menu.buildFromTemplate).mock.calls[0][0];
      const calledLabels = calledTemplate.map((item) => item.label).filter(Boolean);
      expect(calledLabels).toEqual(labels);
    });

    it("triggers correct actions from context menu items", async () => {
      const triggerScoutSpy = vi
        .spyOn(mockWorkerClient, "triggerScout")
        .mockResolvedValue(true);
      const togglePauseSpy = vi
        .spyOn(mockWorkerClient, "togglePause")
        .mockResolvedValue(true);
      const clearIncidentSpy = vi
        .spyOn(mockWorkerClient, "clearIncident")
        .mockResolvedValue(true);

      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );
      const template = trayManager.getContextMenuTemplate();

      // 1. Open Dashboard click
      const openItem = template.find((i) => i.label === "Open Dashboard");
      expect(openItem).toBeDefined();
      openItem!.click!(undefined as any, undefined as any, undefined as any);
      expect(mocks.mockBrowserWindow.show).toHaveBeenCalled();
      expect(mocks.mockBrowserWindow.focus).toHaveBeenCalled();

      // 2. Trigger Scout click
      const scoutItem = template.find((i) => i.label === "Trigger Scout Now");
      expect(scoutItem).toBeDefined();
      await (scoutItem!.click as any)();
      expect(triggerScoutSpy).toHaveBeenCalled();

      // 3. Pause / Resume Agent click
      const pauseItem = template.find((i) => i.label === "Pause / Resume Agent");
      expect(pauseItem).toBeDefined();
      expect(pauseItem!.type).toBe("checkbox");
      expect(pauseItem!.checked).toBe(false);
      await (pauseItem!.click as any)();
      expect(togglePauseSpy).toHaveBeenCalledWith(true);
      expect(trayManager.getIsPaused()).toBe(true);

      // 4. Reset Circuit Breaker click
      const resetItem = template.find(
        (i) => i.label === "Reset Circuit Breaker"
      );
      expect(resetItem).toBeDefined();
      await (resetItem!.click as any)();
      expect(clearIncidentSpy).toHaveBeenCalled();
    });

    it("updates badge count and tooltip properly", () => {
      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );

      // When pendingCount > 0
      trayManager.updateBadge(2);
      expect(trayManager.getPendingCount()).toBe(2);
      expect(mocks.activeTray!.setToolTip).toHaveBeenCalledWith(
        "LinkedIn HITL Agent (2 pending)"
      );
      expect(mocks.activeTray!.setTitle).toHaveBeenCalledWith(" (2)");

      // When pendingCount is 0
      trayManager.updateBadge(0);
      expect(trayManager.getPendingCount()).toBe(0);
      expect(mocks.activeTray!.setToolTip).toHaveBeenCalledWith(
        "LinkedIn HITL Agent"
      );
      expect(mocks.activeTray!.setTitle).toHaveBeenCalledWith("");
    });

    it("updates menu state when paused changes", () => {
      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );
      expect(trayManager.getIsPaused()).toBe(false);

      trayManager.setPaused(true);
      expect(trayManager.getIsPaused()).toBe(true);
      const template = trayManager.getContextMenuTemplate();
      const pauseItem = template.find((i) => i.label === "Pause / Resume Agent");
      expect(pauseItem?.checked).toBe(true);
    });

    it("destroys tray on destroy()", () => {
      const trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );
      const trayRef = mocks.activeTray;
      trayManager.destroy();
      expect(trayRef!.destroy).toHaveBeenCalled();
      expect(trayManager.getTray()).toBeNull();
    });
  });

  describe("PollingEngine", () => {
    let trayManager: TrayManager;

    beforeEach(() => {
      trayManager = new TrayManager(
        mocks.mockBrowserWindow as any,
        mockWorkerClient
      );
    });

    it("polls workerClient and identifies new pending items", async () => {
      const mockState1: AgentState = {
        pending_actions: [
          {
            item_id: "act-1",
            action_type: "approve_comment",
            created_at: "2026-09-29T10:00:00Z",
            draft_text: "Great post!",
          },
          {
            item_id: "act-2",
            action_type: "approve_post",
            created_at: "2026-09-29T10:05:00Z",
            draft_text: "Sharing thoughts...",
          },
        ],
        daily_counters: {
          date: "2026-09-29",
          comments_executed: 0,
          posts_executed: 0,
          suggestions_sent: 2,
        },
        history: [],
        incident: null,
        paused: false,
      };

      vi.spyOn(mockWorkerClient, "fetchState").mockResolvedValue(mockState1);

      const engine = new PollingEngine({
        workerClient: mockWorkerClient,
        trayManager,
        mainWindow: mocks.mockBrowserWindow as any,
        intervalMs: 10_000,
      });

      expect(engine.getSeenPendingIds().size).toBe(0);

      // First poll - both are new
      await engine.pollNow();

      expect(engine.getSeenPendingIds().has("act-1")).toBe(true);
      expect(engine.getSeenPendingIds().has("act-2")).toBe(true);
      expect(engine.getSeenPendingIds().size).toBe(2);
      expect(trayManager.getPendingCount()).toBe(2);
      expect(mocks.notifications.length).toBe(1);

      // Second poll with same items - no new items
      mocks.notifications.length = 0;
      await engine.pollNow();
      expect(mocks.notifications.length).toBe(0);

      // Third poll with a 3rd item
      const mockState2: AgentState = {
        ...mockState1,
        pending_actions: [
          ...mockState1.pending_actions,
          {
            item_id: "act-3",
            action_type: "approve_comment",
            created_at: "2026-09-29T10:10:00Z",
            draft_text: "Another thoughtful comment.",
          },
        ],
      };
      vi.spyOn(mockWorkerClient, "fetchState").mockResolvedValue(mockState2);

      await engine.pollNow();
      expect(engine.getSeenPendingIds().has("act-3")).toBe(true);
      expect(engine.getSeenPendingIds().size).toBe(3);
      expect(trayManager.getPendingCount()).toBe(3);
      expect(mocks.notifications.length).toBe(1);
    });

    it("triggers notification on new items", async () => {
      const mockState: AgentState = {
        pending_actions: [
          {
            item_id: "new-item-1",
            action_type: "approve_comment",
            created_at: "2026-09-29T12:00:00Z",
            draft_text: "Innovative perspective on robotics.",
          },
          {
            item_id: "new-item-2",
            action_type: "approve_comment",
            created_at: "2026-09-29T12:01:00Z",
            draft_text: "Agree with the approach to agent memory.",
          },
        ],
        daily_counters: {
          date: "2026-09-29",
          comments_executed: 1,
          posts_executed: 0,
          suggestions_sent: 3,
        },
        history: [],
        incident: null,
        paused: false,
      };

      vi.spyOn(mockWorkerClient, "fetchState").mockResolvedValue(mockState);

      const engine = new PollingEngine({
        workerClient: mockWorkerClient,
        trayManager,
        mainWindow: mocks.mockBrowserWindow as any,
      });

      await engine.pollNow();

      // Expect Notification to have been constructed
      expect(mocks.activeNotification).not.toBeNull();
      expect(mocks.activeNotification!.title).toBe("LinkedIn HITL Agent");
      expect(mocks.activeNotification!.body).toBe("2 new drafts awaiting your approval");

      // Expect notification show() to have been called
      expect(mocks.activeNotification!.show).toHaveBeenCalled();

      // Test notification click handler
      expect(mocks.activeNotification!.on).toHaveBeenCalledWith(
        "click",
        expect.any(Function)
      );

      const clickCallback = mocks.activeNotification!.on.mock.calls.find(
        (call: any[]) => call[0] === "click"
      )?.[1];
      expect(clickCallback).toBeDefined();

      // Trigger click callback
      clickCallback();

      expect(mocks.mockBrowserWindow.show).toHaveBeenCalled();
      expect(mocks.mockBrowserWindow.focus).toHaveBeenCalled();
      expect(mocks.mockWebContents.send).toHaveBeenCalledWith(
        "navigate:tab",
        "queue"
      );
    });

    it("starts and stops periodic timer cleanly", async () => {
      vi.useFakeTimers();
      const fetchSpy = vi
        .spyOn(mockWorkerClient, "fetchState")
        .mockResolvedValue({
          pending_actions: [],
          daily_counters: {
            date: "2026-09-29",
            comments_executed: 0,
            posts_executed: 0,
            suggestions_sent: 0,
          },
          history: [],
          incident: null,
          paused: false,
        });

      const engine = new PollingEngine({
        workerClient: mockWorkerClient,
        trayManager,
        mainWindow: mocks.mockBrowserWindow as any,
        intervalMs: 60_000,
      });

      expect(engine.getIsRunning()).toBe(false);

      engine.start();
      expect(engine.getIsRunning()).toBe(true);

      // Advance by 60s and flush microtasks
      await vi.advanceTimersByTimeAsync(60_000);
      expect(fetchSpy).toHaveBeenCalledTimes(1);

      // Advance by another 60s and flush microtasks
      await vi.advanceTimersByTimeAsync(60_000);
      expect(fetchSpy).toHaveBeenCalledTimes(2);

      engine.stop();
      expect(engine.getIsRunning()).toBe(false);

      // Advance more - should not call fetchState anymore
      await vi.advanceTimersByTimeAsync(120_000);
      expect(fetchSpy).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });
  });
});
