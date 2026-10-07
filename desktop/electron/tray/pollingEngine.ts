/**
 * Background Polling Engine for LinkedIn HITL Desktop
 *
 * Polls the Cloudflare Worker API at configurable intervals, tracks seen
 * pending actions, updates the system tray badge, and triggers native OS
 * notifications when new items await human approval.
 */

import { BrowserWindow, ipcMain, Notification } from "electron";
import { WorkerClient } from "../api/workerClient";
import { TrayManager } from "./trayManager";
import type { AgentState, PendingAction } from "../types";

export interface PollingEngineOptions {
  workerClient: WorkerClient;
  trayManager: TrayManager;
  mainWindow?: BrowserWindow | null;
  intervalMs?: number;
}

export class PollingEngine {
  private workerClient: WorkerClient;
  private trayManager: TrayManager;
  private mainWindow: BrowserWindow | null;
  private intervalMs: number;
  private timer: NodeJS.Timeout | null = null;
  private isRunning: boolean = false;
  private isPolling: boolean = false;
  private seenPendingIds: Set<string> = new Set();

  constructor(
    optionsOrClient: PollingEngineOptions | WorkerClient,
    trayManager?: TrayManager,
    mainWindow?: BrowserWindow | null,
    intervalMs: number = 300_000
  ) {
    if ("workerClient" in optionsOrClient) {
      this.workerClient = optionsOrClient.workerClient;
      this.trayManager = optionsOrClient.trayManager;
      this.mainWindow = optionsOrClient.mainWindow ?? null;
      this.intervalMs = optionsOrClient.intervalMs ?? 300_000;
    } else {
      this.workerClient = optionsOrClient;
      this.trayManager = trayManager!;
      this.mainWindow = mainWindow ?? null;
      this.intervalMs = intervalMs;
    }
  }

  public setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
  }

  public getMainWindow(): BrowserWindow | null {
    return this.mainWindow;
  }

  public getSeenPendingIds(): Set<string> {
    return this.seenPendingIds;
  }

  public getIntervalMs(): number {
    return this.intervalMs;
  }

  public setIntervalMs(ms: number): void {
    this.intervalMs = ms;
    if (this.isRunning) {
      this.stop();
      this.start(false);
    }
  }

  public getIsRunning(): boolean {
    return this.isRunning;
  }

  /**
   * Starts periodic polling at the configured interval.
   */
  public start(immediate = false): void {
    if (this.isRunning) return;
    this.isRunning = true;

    this.timer = setInterval(() => {
      this.pollNow().catch((err) => {
        console.error("PollingEngine: interval poll error:", err);
      });
    }, this.intervalMs);

    if (immediate) {
      this.pollNow().catch((err) => {
        console.error("PollingEngine: immediate poll error:", err);
      });
    }
  }

  /**
   * Stops the background polling timer.
   */
  public stop(): void {
    this.isRunning = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /**
   * Executes a single poll against workerClient.fetchState(), detects new items,
   * updates the tray badge, and triggers native notifications if new items exist.
   */
  public async pollNow(): Promise<void> {
    if (this.isPolling) return;
    this.isPolling = true;

    try {
      const state: AgentState = await this.workerClient.fetchState();
      const pendingActions: PendingAction[] =
        state?.pending_actions ||
        state?.pendingActions ||
        state?.pending ||
        [];

      // Update paused state in tray if present in state response
      if (typeof state?.paused === "boolean") {
        this.trayManager.setPaused(state.paused);
      }

      // Always update tray badge with current count
      this.trayManager.updateBadge(pendingActions.length);

      // Notify renderer of polled queue update
      if (
        this.mainWindow &&
        (typeof this.mainWindow.isDestroyed !== "function" || !this.mainWindow.isDestroyed()) &&
        this.mainWindow.webContents
      ) {
        this.mainWindow.webContents.send("realtime:event", {
          type: "queue_updated",
          state,
        });
      }

      // Identify new pending items (item_id not in seen set)
      const newItems: PendingAction[] = [];
      for (const item of pendingActions) {
        if (item && item.item_id && !this.seenPendingIds.has(item.item_id)) {
          newItems.push(item);
        }
      }

      // Update seen set with all current pending item IDs
      for (const item of pendingActions) {
        if (item && item.item_id) {
          this.seenPendingIds.add(item.item_id);
        }
      }

      // When new pending items are detected (count > 0):
      const newCount = newItems.length;
      if (newCount > 0) {
        this.trayManager.updateBadge(pendingActions.length);

        const notification = new Notification({
          title: "LinkedAide",
          body: `${newCount} new draft${newCount > 1 ? "s" : ""} awaiting your approval`,
        });

        notification.on("click", () => {
          if (this.mainWindow) {
            if (this.mainWindow.isMinimized()) {
              this.mainWindow.restore();
            }
            this.mainWindow.show();
            this.mainWindow.focus();

            if (
              this.mainWindow.webContents &&
              (typeof this.mainWindow.webContents.isDestroyed !== "function" ||
                !this.mainWindow.webContents.isDestroyed())
            ) {
              this.mainWindow.webContents.send("navigate:tab", "queue");
            }
          }
          try {
            ipcMain.emit("navigate:tab", null, "queue");
          } catch {
            // no-op if ipcMain is not bound
          }
        });

        notification.show();
      }
    } catch (err) {
      console.error("PollingEngine: error fetching state:", err);
    } finally {
      this.isPolling = false;
    }
  }
}
