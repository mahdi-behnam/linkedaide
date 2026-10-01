/**
 * Electron Main Process
 *
 * Configures secure BrowserWindow, registers IPC handlers, manages local
 * settings persistence, and forwards Worker API requests.
 */

import { app, BrowserWindow, ipcMain, session } from "electron";
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { WorkerClient } from "./api/workerClient";
import { RealtimePushClient } from "./api/realtimeHub";
import { captureLinkedInSession } from "./auth/linkedinAuth";
import {
  decryptSession,
  encryptSession,
  generateFernetKey,
} from "./crypto/fernet";
import { TrayManager } from "./tray/trayManager";
import { PollingEngine } from "./tray/pollingEngine";
import type { ActionResult, DesktopSettings } from "./types";

interface QuittableApp extends Electron.App {
  isQuitting?: boolean;
}
const mainApp = app as QuittableApp;
mainApp.isQuitting = false;

let mainWindow: BrowserWindow | null = null;
let workerClient: WorkerClient;
let realtimeClient: RealtimePushClient | null = null;
let trayManager: TrayManager | null = null;
let pollingEngine: PollingEngine | null = null;

function getSettingsPath(): string {
  return path.join(app.getPath("userData"), "settings.json");
}

function loadSettings(): DesktopSettings {
  const defaults: DesktopSettings = {
    workerUrl: process.env.WORKER_URL || "",
    apiSecret: process.env.DESKTOP_API_SECRET || "",
    encryptionKey: process.env.SESSION_ENCRYPTION_KEY || "",
    nimModel: process.env.NIM_MODEL_PRIMARY || "meta/llama-3.1-70b-instruct",
    nimApiKey: process.env.NVIDIA_NIM_API_KEY || "",
    githubRepoOwner: process.env.GITHUB_REPO_OWNER || "mahdi-behnam",
    githubRepoName: process.env.GITHUB_REPO_NAME || "linkedin-hitl-agent",
    githubDispatchPat: process.env.GITHUB_DISPATCH_PAT || "",
    autoRefreshInterval: 30,
    executionMode: "cloud",
    headless: true,
    minimizeToTray: true,
    notificationsEnabled: true,
    maxCommentsPerDay: 15,
    maxPostsPerDay: 3,
    maxSuggestionsPerRun: 10,
    actionTtlHours: 24,
  };

  try {
    const settingsPath = getSettingsPath();
    if (fs.existsSync(settingsPath)) {
      const data = fs.readFileSync(settingsPath, "utf-8");
      const parsed = JSON.parse(data);
      return { ...defaults, ...parsed };
    }
  } catch (err) {
    console.error("Failed to load desktop settings:", err);
  }

  return defaults;
}

function saveSettings(settings: Partial<DesktopSettings>): boolean {
  try {
    const current = loadSettings();
    const updated: DesktopSettings = { ...current, ...settings };
    if (updated.workerUrl) {
      updated.workerUrl = workerClient.normalizeUrl(updated.workerUrl);
    }
    if (updated.apiSecret) {
      updated.apiSecret = updated.apiSecret.trim();
    }
    if (updated.nimModel !== undefined) {
      updated.nimModel = updated.nimModel.trim();
    }
    if (updated.nimApiKey !== undefined) {
      updated.nimApiKey = updated.nimApiKey.trim();
    }
    if (updated.githubRepoOwner !== undefined) {
      updated.githubRepoOwner = updated.githubRepoOwner.trim();
    }
    if (updated.githubRepoName !== undefined) {
      updated.githubRepoName = updated.githubRepoName.trim();
    }
    if (updated.githubDispatchPat !== undefined) {
      updated.githubDispatchPat = updated.githubDispatchPat.trim();
    }
    const settingsPath = getSettingsPath();
    const dir = path.dirname(settingsPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(settingsPath, JSON.stringify(updated, null, 2), "utf-8");

    workerClient.updateConfig({
      baseUrl: updated.workerUrl,
      apiSecret: updated.apiSecret,
    });

    if (realtimeClient) {
      realtimeClient.updateCredentials(updated.workerUrl, updated.apiSecret);
    }

    if (updated.autoRefreshInterval && pollingEngine) {
      pollingEngine.setIntervalMs(updated.autoRefreshInterval * 1000);
    }

    return true;
  } catch (err) {
    console.error("Failed to save desktop settings:", err);
    return false;
  }
}

function registerIpcHandlers(): void {
  // Cloudflare Worker & Local Runner API Handlers
  ipcMain.handle(
    "api:testConnection",
    async (_event, credentials?: { workerUrl?: string; apiSecret?: string }) => {
      const result = await workerClient.testConnection({
        baseUrl: credentials?.workerUrl,
        apiSecret: credentials?.apiSecret,
      });
      if (result.success && credentials?.workerUrl && credentials?.apiSecret) {
        if (realtimeClient) {
          realtimeClient.updateCredentials(
            credentials.workerUrl,
            credentials.apiSecret
          );
        }
      }
      return result;
    }
  );

  ipcMain.handle(
    "api:fetchState",
    async (_event, credentials?: { workerUrl?: string; apiSecret?: string }) => {
      if (credentials?.workerUrl || credentials?.apiSecret) {
        workerClient.updateConfig({
          baseUrl: credentials.workerUrl,
          apiSecret: credentials.apiSecret,
        });
      }
      return await workerClient.fetchState();
    }
  );

  ipcMain.handle(
    "api:executeAction",
    async (_event, action: "approve" | "reject", itemId: string) => {
      const settings = loadSettings();
      if (settings.executionMode === "local" && action === "approve") {
        return new Promise<ActionResult>((resolve) => {
          const repoRoot = path.resolve(__dirname, "../..");
          const child = spawn("uv", ["run", "agent", "execute", "--action-id", itemId], {
            cwd: repoRoot,
            env: {
              ...process.env,
              HEADLESS: String(settings.headless ?? true),
              ...(settings.nimApiKey ? { NVIDIA_NIM_API_KEY: settings.nimApiKey } : {}),
              ...(settings.nimModel ? { NIM_MODEL_PRIMARY: settings.nimModel } : {}),
            },
          });
          child.on("close", (code) => {
            resolve({
              success: code === 0,
              itemId,
              action,
              message: code === 0 ? "Local execution completed" : "Local execution failed",
            });
          });
          child.on("error", (err) => {
            resolve({
              success: false,
              itemId,
              action,
              error: err.message,
            });
          });
        });
      }
      return await workerClient.executeAction(action, itemId, {
        repo_owner: settings.githubRepoOwner,
        repo_name: settings.githubRepoName,
        github_pat: settings.githubDispatchPat,
      });
    }
  );

  ipcMain.handle(
    "api:executeConnectionAction",
    async (_event, action: "approve" | "reject", id: string, _note?: string) => {
      const settings = loadSettings();
      return await workerClient.executeAction(action, id, {
        repo_owner: settings.githubRepoOwner,
        repo_name: settings.githubRepoName,
        github_pat: settings.githubDispatchPat,
      });
    }
  );

  ipcMain.handle("api:triggerScout", async () => {
    const settings = loadSettings();
    if (settings.executionMode === "local") {
      return new Promise<boolean>((resolve) => {
        const repoRoot = path.resolve(__dirname, "../..");
        const child = spawn("uv", ["run", "agent", "scout"], {
          cwd: repoRoot,
          env: {
            ...process.env,
            HEADLESS: String(settings.headless ?? true),
            ...(settings.nimApiKey ? { NVIDIA_NIM_API_KEY: settings.nimApiKey } : {}),
            ...(settings.nimModel ? { NIM_MODEL_PRIMARY: settings.nimModel } : {}),
          },
        });
        child.on("close", (code) => {
          resolve(code === 0);
        });
        child.on("error", () => {
          resolve(false);
        });
      });
    }
    return await workerClient.triggerScout({
      repo_owner: settings.githubRepoOwner,
      repo_name: settings.githubRepoName,
      github_pat: settings.githubDispatchPat,
    });
  });

  ipcMain.handle("api:togglePause", async (_event, paused: boolean) => {
    return await workerClient.togglePause(paused);
  });

  ipcMain.handle("api:clearIncident", async () => {
    return await workerClient.clearIncident();
  });

  ipcMain.handle(
    "api:rewriteDraft",
    async (_event, draftText: string, tone: string) => {
      return await workerClient.rewriteDraft(draftText, tone);
    }
  );

  ipcMain.handle("api:saveSession", async (_event, sessionData: string) => {
    return await workerClient.saveSession(sessionData);
  });

  // Local Settings Handlers
  ipcMain.handle("settings:get", async () => {
    return loadSettings();
  });

  ipcMain.handle(
    "settings:save",
    async (_event, settings: Partial<DesktopSettings>) => {
      return saveSettings(settings);
    }
  );

  // Fernet Cryptography Handlers
  ipcMain.handle(
    "crypto:encryptSession",
    async (_event, data: string, base64Key: string) => {
      return encryptSession(data, base64Key);
    }
  );

  ipcMain.handle(
    "crypto:decryptSession",
    async (_event, token: string, base64Key: string) => {
      return decryptSession(token, base64Key);
    }
  );

  ipcMain.handle("crypto:generateFernetKey", async () => {
    return generateFernetKey();
  });

  // LinkedIn Auth Handlers
  ipcMain.handle("auth:captureSession", async () => {
    const settings = loadSettings();
    if (!settings.encryptionKey) {
      return { success: false, error: "Session encryption key not configured in settings" };
    }
    const targetWin = mainWindow || BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    return await captureLinkedInSession(
      targetWin,
      settings.encryptionKey,
      async (data: string) => {
        return await workerClient.saveSession(data);
      }
    );
  });

  ipcMain.handle("auth:checkSessionHealth", async () => {
    try {
      const cookies = await session.defaultSession.cookies.get({ name: "li_at" });
      const liAt = cookies.find(
        (c) => c.domain?.includes("linkedin.com") || c.name === "li_at"
      );
      if (liAt && liAt.value) {
        let daysRemaining = 18;
        if (typeof liAt.expirationDate === "number") {
          const days = Math.round(
            (liAt.expirationDate * 1000 - Date.now()) / (1000 * 60 * 60 * 24)
          );
          if (days > 0) {
            daysRemaining = days;
          }
        }
        return { valid: true, daysRemaining, details: "Active li_at cookie" };
      }
    } catch {
      // Fallback if session check encounters an error
    }

    return { valid: false, daysRemaining: 0, details: "No active LinkedIn session found in storage" };
  });

  // NVIDIA NIM Models Fetcher
  ipcMain.handle("llm:fetchNimModels", async (_event, apiKey?: string) => {
    try {
      const activeKey = (apiKey || loadSettings().nimApiKey || "").trim();
      const headers: Record<string, string> = {
        Accept: "application/json",
      };
      if (activeKey) {
        headers["Authorization"] = `Bearer ${activeKey}`;
      }

      const response = await fetch("https://integrate.api.nvidia.com/v1/models", {
        method: "GET",
        headers,
      });

      if (!response.ok) {
        return {
          success: false,
          models: [],
          error: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      const json = (await response.json()) as { data?: Array<{ id: string }> };
      if (!json.data || !Array.isArray(json.data)) {
        return {
          success: false,
          models: [],
          error: "Invalid response format from NVIDIA API",
        };
      }

      const models = json.data
        .map((m) => m.id)
        .filter((id): id is string => typeof id === "string" && id.length > 0)
        .sort((a, b) => a.localeCompare(b));

      return {
        success: true,
        models,
      };
    } catch (err: any) {
      return {
        success: false,
        models: [],
        error: err.message || "Failed to reach NVIDIA API",
      };
    }
  });
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1000,
    minHeight: 650,
    backgroundColor: "#09090b",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  win.once("ready-to-show", () => {
    win.show();
  });

  win.on("close", (event) => {
    const settings = loadSettings();
    const shouldMinimize = settings.minimizeToTray ?? true;
    if (!mainApp.isQuitting && trayManager && shouldMinimize) {
      event.preventDefault();
      win.hide();
      return false;
    }
  });

  const isDev =
    !app.isPackaged &&
    Boolean(
      process.env.VITE_DEV_SERVER_URL ||
        process.env.NODE_ENV === "development" ||
        !fs.existsSync(path.join(__dirname, "../dist/index.html"))
    );

  if (isDev) {
    const devUrl = process.env.VITE_DEV_SERVER_URL || "http://localhost:5173";
    win.loadURL(devUrl).catch(() => {
      const prodPath = path.join(__dirname, "../dist/index.html");
      if (fs.existsSync(prodPath)) {
        win.loadFile(prodPath);
      }
    });
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  return win;
}

app.whenReady().then(() => {
  const settings = loadSettings();
  workerClient = new WorkerClient({
    baseUrl: settings.workerUrl,
    apiSecret: settings.apiSecret,
  });

  registerIpcHandlers();
  mainWindow = createWindow();

  trayManager = new TrayManager(mainWindow, workerClient);
  pollingEngine = new PollingEngine({
    workerClient,
    trayManager,
    mainWindow,
  });
  pollingEngine.start();

  realtimeClient = new RealtimePushClient(
    mainWindow,
    settings.workerUrl,
    settings.apiSecret
  );
  realtimeClient.connect();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createWindow();
      if (trayManager) {
        trayManager.setMainWindow(mainWindow);
      }
      if (pollingEngine) {
        pollingEngine.setMainWindow(mainWindow);
      }
      if (realtimeClient) {
        realtimeClient.setMainWindow(mainWindow);
      }
    } else if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

app.on("before-quit", () => {
  mainApp.isQuitting = true;
  if (pollingEngine) {
    pollingEngine.stop();
    pollingEngine = null;
  }
  if (trayManager) {
    trayManager.destroy();
    trayManager = null;
  }
  if (realtimeClient) {
    realtimeClient.disconnect();
    realtimeClient = null;
  }
});

app.on("window-all-closed", () => {
  if (!trayManager || mainApp.isQuitting) {
    if (process.platform !== "darwin") {
      app.quit();
    }
  }
});
