import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mocks = vi.hoisted(() => {
  const handlers = new Map<string, Function>();
  const ipcMain = {
    handle: vi.fn((channel: string, handler: Function) => {
      handlers.set(channel, handler);
    }),
    handlers,
  };

  const mockWebContents = {
    send: vi.fn(),
  };

  const mockBrowserWindow = {
    webContents: mockWebContents,
    isDestroyed: vi.fn().mockReturnValue(false),
    reload: vi.fn(),
  };

  const eventListeners = new Map<string, Function[]>();

  const mockAutoUpdater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: vi.fn().mockResolvedValue(null),
    downloadUpdate: vi.fn().mockResolvedValue(null),
    quitAndInstall: vi.fn(),
    on: vi.fn((event: string, cb: Function) => {
      if (!eventListeners.has(event)) {
        eventListeners.set(event, []);
      }
      eventListeners.get(event)!.push(cb);
      return mockAutoUpdater;
    }),
    emit: (event: string, ...args: any[]) => {
      const cbs = eventListeners.get(event) || [];
      for (const cb of cbs) {
        cb(...args);
      }
    },
    eventListeners,
  };

  class MockCancellationToken {
    cancelled = false;
    cancel = vi.fn(() => {
      this.cancelled = true;
    });
  }

  return {
    ipcMain,
    mockWebContents,
    mockBrowserWindow,
    mockAutoUpdater,
    MockCancellationToken,
  };
});

vi.mock("electron", () => ({
  app: {
    isPackaged: true,
  },
  BrowserWindow: mocks.mockBrowserWindow,
  ipcMain: mocks.ipcMain,
}));

vi.mock("electron-updater", () => ({
  autoUpdater: mocks.mockAutoUpdater,
  CancellationToken: mocks.MockCancellationToken,
}));

import { UpdateManager } from "../electron/updater/updateManager";

describe("UpdateManager", () => {
  let manager: UpdateManager;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.ipcMain.handlers.clear();
    manager = new UpdateManager({
      mainWindow: mocks.mockBrowserWindow as any,
      simulate: true,
    });
  });

  afterEach(() => {
    manager.destroy();
  });

  it("initializes with idle state and registers IPC handlers", () => {
    expect(manager.getState()).toEqual({
      status: "idle",
      info: null,
      progress: null,
      error: null,
    });

    expect(mocks.ipcMain.handle).toHaveBeenCalledWith(
      "updater:getStatus",
      expect.any(Function),
    );
    expect(mocks.ipcMain.handle).toHaveBeenCalledWith(
      "updater:checkForUpdates",
      expect.any(Function),
    );
    expect(mocks.ipcMain.handle).toHaveBeenCalledWith(
      "updater:startDownload",
      expect.any(Function),
    );
    expect(mocks.ipcMain.handle).toHaveBeenCalledWith(
      "updater:cancelDownload",
      expect.any(Function),
    );
    expect(mocks.ipcMain.handle).toHaveBeenCalledWith(
      "updater:quitAndInstall",
      expect.any(Function),
    );
  });

  it("simulates checking and finding an update", async () => {
    vi.useFakeTimers();

    await manager.checkForUpdates();
    expect(manager.getState().status).toBe("checking");

    // Fast-forward simulation delay
    vi.advanceTimersByTime(1500);

    const state = manager.getState();
    expect(state.status).toBe("available");
    expect(state.info?.version).toBe("1.3.1");
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith(
      "updater:event",
      expect.objectContaining({ status: "available" }),
    );

    vi.useRealTimers();
  });

  it("simulates downloading with live progress telemetry", async () => {
    vi.useFakeTimers();

    await manager.startDownload();
    expect(manager.getState().status).toBe("downloading");

    // Advance 3 ticks
    vi.advanceTimersByTime(350 * 3);

    let state = manager.getState();
    expect(state.status).toBe("downloading");
    expect(state.progress).toBeTruthy();
    expect(state.progress?.percent).toBeGreaterThan(0);
    expect(state.progress?.transferred).toBeGreaterThan(0);
    expect(state.progress?.bytesPerSecond).toBeGreaterThan(0);

    // Advance past completion
    vi.advanceTimersByTime(350 * 25);

    state = manager.getState();
    expect(state.status).toBe("downloaded");

    vi.useRealTimers();
  });

  it("cancels simulated download and reverts to available", async () => {
    vi.useFakeTimers();

    await manager.startDownload();
    expect(manager.getState().status).toBe("downloading");

    const cancelled = manager.cancelDownload();
    expect(cancelled).toBe(true);

    const state = manager.getState();
    expect(state.status).toBe("available");
    expect(state.progress).toBeNull();

    vi.useRealTimers();
  });

  it("executes simulated quitAndInstall by reloading window", () => {
    const success = manager.quitAndInstall();
    expect(success).toBe(true);
    expect(mocks.mockBrowserWindow.reload).toHaveBeenCalled();
  });

  it("responds to IPC handler calls", async () => {
    const getStatusHandler = mocks.ipcMain.handlers.get("updater:getStatus");
    expect(getStatusHandler).toBeDefined();
    expect(getStatusHandler!()).toEqual(manager.getState());

    const cancelHandler = mocks.ipcMain.handlers.get("updater:cancelDownload");
    expect(cancelHandler).toBeDefined();
    expect(cancelHandler!()).toBe(true);
  });
});
