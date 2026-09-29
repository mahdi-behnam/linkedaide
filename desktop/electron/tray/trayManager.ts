/**
 * System Tray Manager for LinkedIn HITL Desktop
 *
 * Manages the Electron Tray lifecycle, status badge tooltips,
 * context menu actions, and window visibility toggling.
 */

import {
  app,
  BrowserWindow,
  Menu,
  MenuItemConstructorOptions,
  nativeImage,
  NativeImage,
  Tray,
} from "electron";
import { WorkerClient } from "../api/workerClient";

/**
 * 16x16 RGBA PNG base64 Data URL
 * Dark rounded square (#18181b) with an emerald dot (#10b981)
 * Used headlessly without missing asset errors.
 */
export const FALLBACK_TRAY_ICON_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAPElEQVR4nGNgoBaQkJD+TwqmSDOGIYPXAIGdjXBMsgHImnEZgtMAbJqxGTKIDaA4DKgSC/RNSBRnJkoAAMRhHGvI2FCfAAAAAElFTkSuQmCC";

export function createFallbackTrayIcon(): NativeImage {
  return nativeImage.createFromDataURL(FALLBACK_TRAY_ICON_DATA_URL);
}

export interface TrayManagerOptions {
  mainWindow?: BrowserWindow | null;
  workerClient: WorkerClient;
  initialPaused?: boolean;
}

export class TrayManager {
  private tray: Tray | null = null;
  private mainWindow: BrowserWindow | null = null;
  private workerClient: WorkerClient;
  private isPaused: boolean = false;
  private pendingCount: number = 0;

  constructor(
    mainWindowOrOptions?: BrowserWindow | null | TrayManagerOptions,
    workerClient?: WorkerClient,
    initialPaused: boolean = false
  ) {
    if (
      mainWindowOrOptions &&
      typeof mainWindowOrOptions === "object" &&
      "workerClient" in mainWindowOrOptions
    ) {
      this.mainWindow = mainWindowOrOptions.mainWindow ?? null;
      this.workerClient = mainWindowOrOptions.workerClient;
      this.isPaused = mainWindowOrOptions.initialPaused ?? false;
    } else {
      this.mainWindow = (mainWindowOrOptions as BrowserWindow | null) ?? null;
      this.workerClient = workerClient!;
      this.isPaused = initialPaused;
    }

    this.initTray();
  }

  /**
   * Initializes the Tray instance with the fallback icon and default context menu.
   */
  private initTray(): void {
    const icon = createFallbackTrayIcon();
    this.tray = new Tray(icon);
    this.tray.setToolTip("LinkedIn HITL Agent");
    this.updateContextMenu();

    this.tray.on("click", () => {
      this.openDashboard();
    });
  }

  /**
   * Updates the reference to the main application window.
   */
  public setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
  }

  public getMainWindow(): BrowserWindow | null {
    return this.mainWindow;
  }

  public getTray(): Tray | null {
    return this.tray;
  }

  public getIsPaused(): boolean {
    return this.isPaused;
  }

  public getPendingCount(): number {
    return this.pendingCount;
  }

  /**
   * Restores, shows, and focuses the main application window.
   */
  public openDashboard(): void {
    if (this.mainWindow) {
      if (this.mainWindow.isMinimized()) {
        this.mainWindow.restore();
      }
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  /**
   * Constructs the MenuItem template for the tray context menu.
   */
  public getContextMenuTemplate(): MenuItemConstructorOptions[] {
    return [
      {
        label: "Open Dashboard",
        click: () => {
          this.openDashboard();
        },
      },
      {
        label: "Trigger Scout Now",
        click: async () => {
          try {
            await this.workerClient.triggerScout();
          } catch (err) {
            console.error("TrayManager: failed to trigger scout:", err);
          }
        },
      },
      {
        label: "Pause / Resume Agent",
        type: "checkbox",
        checked: this.isPaused,
        click: async () => {
          const nextState = !this.isPaused;
          try {
            await this.workerClient.togglePause(nextState);
            this.setPaused(nextState);
          } catch (err) {
            console.error("TrayManager: failed to toggle pause:", err);
          }
        },
      },
      {
        label: "Reset Circuit Breaker",
        click: async () => {
          try {
            await this.workerClient.clearIncident();
          } catch (err) {
            console.error("TrayManager: failed to reset circuit breaker:", err);
          }
        },
      },
      {
        type: "separator",
      },
      {
        label: "Quit",
        click: () => {
          app.quit();
        },
      },
    ];
  }

  /**
   * Builds and sets the context menu on the tray instance.
   */
  public updateContextMenu(): void {
    if (
      this.tray &&
      (typeof this.tray.isDestroyed !== "function" || !this.tray.isDestroyed())
    ) {
      const template = this.getContextMenuTemplate();
      const menu = Menu.buildFromTemplate(template);
      this.tray.setContextMenu(menu);
    }
  }

  /**
   * Updates the tray tooltip and macOS menu bar title with the pending count.
   */
  public updateBadge(pendingCount: number): void {
    this.pendingCount = Math.max(0, pendingCount);
    const tooltip =
      this.pendingCount > 0
        ? `LinkedIn HITL Agent (${this.pendingCount} pending)`
        : "LinkedIn HITL Agent";
    const title = this.pendingCount > 0 ? ` (${this.pendingCount})` : "";

    if (
      this.tray &&
      (typeof this.tray.isDestroyed !== "function" || !this.tray.isDestroyed())
    ) {
      this.tray.setToolTip(tooltip);
      if (typeof this.tray.setTitle === "function") {
        this.tray.setTitle(title);
      }
    }
  }

  /**
   * Updates the paused state and rebuilds the context menu.
   */
  public setPaused(isPaused: boolean): void {
    this.isPaused = isPaused;
    this.updateContextMenu();
  }

  /**
   * Cleans up the tray instance on application shutdown.
   */
  public destroy(): void {
    if (this.tray) {
      if (
        typeof this.tray.isDestroyed !== "function" ||
        !this.tray.isDestroyed()
      ) {
        this.tray.destroy();
      }
      this.tray = null;
    }
  }
}
