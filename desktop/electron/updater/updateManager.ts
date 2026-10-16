/**
 * Electron Update Manager
 *
 * Orchestrates automated application update checks on startup,
 * manages the download lifecycle and live telemetry, and provides
 * safe restart-to-install execution.
 */

import { app, BrowserWindow, ipcMain } from "electron";
import { autoUpdater, CancellationToken } from "electron-updater";
import type { UpdateProgress, UpdateState } from "../types";

export interface UpdateManagerOptions {
  mainWindow: BrowserWindow | null;
  simulate?: boolean;
}

export class UpdateManager {
  private mainWindow: BrowserWindow | null = null;
  private cancellationToken: CancellationToken | null = null;
  private simulationInterval: NodeJS.Timeout | null = null;
  private isSimulation: boolean = false;

  private state: UpdateState = {
    status: "idle",
    info: null,
    progress: null,
    error: null,
  };

  constructor(options?: UpdateManagerOptions) {
    if (options?.mainWindow) {
      this.mainWindow = options.mainWindow;
    }

    this.isSimulation =
      options?.simulate ??
      (process.env.SIMULATE_UPDATE === "true" || process.env.NODE_ENV === "test");

    this.configureAutoUpdater();
    this.registerIpcHandlers();
  }

  public setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
  }

  public getState(): UpdateState {
    return { ...this.state };
  }

  private configureAutoUpdater(): void {
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = false;

    autoUpdater.on("checking-for-update", () => {
      this.state.status = "checking";
      this.state.error = null;
      this.broadcastState();
    });

    autoUpdater.on("update-available", (info) => {
      this.state.status = "available";
      this.state.info = {
        version: info.version,
        releaseDate: info.releaseDate,
        releaseNotes:
          typeof info.releaseNotes === "string"
            ? info.releaseNotes
            : Array.isArray(info.releaseNotes)
            ? info.releaseNotes.map((n) => (typeof n === "string" ? n : n.note || "")).join("\n")
            : undefined,
        releaseName: info.releaseName || undefined,
      };
      this.state.error = null;
      this.broadcastState();
    });

    autoUpdater.on("update-not-available", () => {
      this.state.status = "idle";
      this.broadcastState();
    });

    autoUpdater.on("error", (err) => {
      this.state.status = "error";
      this.state.error = err ? err.message || String(err) : "Unknown update error";
      this.broadcastState();
    });

    autoUpdater.on("download-progress", (progressObj) => {
      const bytesPerSecond = progressObj.bytesPerSecond || 0;
      const transferred = progressObj.transferred || 0;
      const total = progressObj.total || 0;
      const remainingBytes = Math.max(0, total - transferred);
      const etaSeconds =
        bytesPerSecond > 0 ? Math.round(remainingBytes / bytesPerSecond) : 0;

      const progress: UpdateProgress = {
        percent: Math.round((progressObj.percent || 0) * 10) / 10,
        bytesPerSecond,
        transferred,
        total,
        remainingBytes,
        etaSeconds,
      };

      this.state.status = "downloading";
      this.state.progress = progress;
      this.broadcastState();
    });

    autoUpdater.on("update-downloaded", (info) => {
      this.state.status = "downloaded";
      if (!this.state.info && info) {
        this.state.info = {
          version: info.version,
          releaseDate: info.releaseDate,
          releaseName: info.releaseName || undefined,
        };
      }
      this.broadcastState();
    });
  }

  public async checkForUpdates(): Promise<boolean> {
    if (this.isSimulation) {
      this.state.status = "checking";
      this.broadcastState();

      setTimeout(() => {
        this.state.status = "available";
        this.state.info = {
          version: "1.3.1",
          releaseDate: new Date().toISOString(),
          releaseName: "LinkedAide 1.3.1 - Performance & Telemetry Update",
          releaseNotes:
            "- Enhanced startup update checks with live telemetry\n- Fine-grained progress tracking (speed, ETA, remaining bytes)\n- Apple Human Interface Guidelines aesthetic refinement",
        };
        this.broadcastState();
      }, 1200);

      return true;
    }

    if (!app.isPackaged && !process.env.TEST_UPDATER) {
      // In unpackaged development mode without test flags, skip calling GitHub
      return false;
    }

    try {
      await autoUpdater.checkForUpdates();
      return true;
    } catch (err) {
      console.warn("Failed to check for updates:", err);
      return false;
    }
  }

  public async startDownload(): Promise<boolean> {
    if (this.state.status === "downloading") {
      return true;
    }

    if (this.isSimulation) {
      this.state.status = "downloading";
      const totalBytes = 54.8 * 1024 * 1024; // ~54.8 MB
      let transferred = 0;
      const totalSteps = 25;
      let step = 0;

      if (this.simulationInterval) {
        clearInterval(this.simulationInterval);
      }

      this.simulationInterval = setInterval(() => {
        step++;
        const simulatedSpeed = (3.2 + Math.sin(step) * 0.8) * 1024 * 1024; // ~2.4 - 4.0 MB/s
        transferred = Math.min(totalBytes, (totalBytes / totalSteps) * step);
        const percent = Math.round((transferred / totalBytes) * 1000) / 10;
        const remainingBytes = Math.max(0, totalBytes - transferred);
        const etaSeconds =
          simulatedSpeed > 0 ? Math.max(1, Math.round(remainingBytes / simulatedSpeed)) : 0;

        this.state.progress = {
          percent,
          bytesPerSecond: simulatedSpeed,
          transferred: Math.round(transferred),
          total: totalBytes,
          remainingBytes: Math.round(remainingBytes),
          etaSeconds: step >= totalSteps ? 0 : etaSeconds,
        };

        if (step >= totalSteps) {
          if (this.simulationInterval) {
            clearInterval(this.simulationInterval);
            this.simulationInterval = null;
          }
          this.state.status = "downloaded";
        }

        this.broadcastState();
      }, 350);

      return true;
    }

    try {
      this.cancellationToken = new CancellationToken();
      this.state.status = "downloading";
      this.broadcastState();
      await autoUpdater.downloadUpdate(this.cancellationToken);
      return true;
    } catch (err: any) {
      if (err?.name === "CancellationError" || err?.message?.includes("cancelled")) {
        this.state.status = "available";
      } else {
        this.state.status = "error";
        this.state.error = err?.message || "Failed to download update";
      }
      this.broadcastState();
      return false;
    }
  }

  public cancelDownload(): boolean {
    if (this.isSimulation) {
      if (this.simulationInterval) {
        clearInterval(this.simulationInterval);
        this.simulationInterval = null;
      }
      this.state.status = "available";
      this.state.progress = null;
      this.broadcastState();
      return true;
    }

    if (this.cancellationToken) {
      this.cancellationToken.cancel();
      this.cancellationToken = null;
      this.state.status = "available";
      this.state.progress = null;
      this.broadcastState();
      return true;
    }

    return false;
  }

  public quitAndInstall(): boolean {
    if (this.isSimulation) {
      console.log("[Simulation] quitAndInstall invoked. Restarting application...");
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.reload();
      }
      return true;
    }

    try {
      autoUpdater.quitAndInstall(false, true);
      return true;
    } catch (err) {
      console.error("Failed to quit and install update:", err);
      return false;
    }
  }

  private registerIpcHandlers(): void {
    ipcMain.handle("updater:getStatus", () => {
      return this.getState();
    });

    ipcMain.handle("updater:startDownload", async () => {
      return await this.startDownload();
    });

    ipcMain.handle("updater:cancelDownload", () => {
      return this.cancelDownload();
    });

    ipcMain.handle("updater:quitAndInstall", () => {
      return this.quitAndInstall();
    });
  }

  private broadcastState(): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      try {
        this.mainWindow.webContents.send("updater:event", this.getState());
      } catch (err) {
        console.warn("Failed to broadcast updater state:", err);
      }
    }
  }

  public destroy(): void {
    if (this.simulationInterval) {
      clearInterval(this.simulationInterval);
      this.simulationInterval = null;
    }
  }
}
