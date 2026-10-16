/**
 * Electron Main Process
 *
 * Configures secure BrowserWindow, registers IPC handlers, manages local
 * settings persistence, and forwards Worker API requests.
 */

import { app, BrowserWindow, ipcMain, Menu, session, shell } from "electron";
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
import { setupAppMenu } from "./menu";
import { UpdateManager } from "./updater/updateManager";
import type { ActionResult, DesktopSettings } from "./types";

interface QuittableApp extends Electron.App {
  isQuitting?: boolean;
}
const mainApp = app as QuittableApp;
mainApp.isQuitting = false;

// Set Application User Model ID for Windows taskbar grouping and custom icon binding
if (process.platform === "win32") {
  app.setAppUserModelId("com.linkedaide.desktop");
}

let mainWindow: BrowserWindow | null = null;
let workerClient: WorkerClient;
let realtimeClient: RealtimePushClient | null = null;
let trayManager: TrayManager | null = null;
let pollingEngine: PollingEngine | null = null;
let updateManager: UpdateManager | null = null;

function getSettingsPath(): string {
  return path.join(app.getPath("userData"), "settings.json");
}

function loadSettings(): DesktopSettings {
  const defaults: DesktopSettings = {
    workerUrl: process.env.WORKER_URL || "",
    apiSecret: process.env.DESKTOP_API_SECRET || "",
    encryptionKey: process.env.SESSION_ENCRYPTION_KEY || "",
    nimModel:
      process.env.NIM_MODEL_PRIMARY || "nvidia/nemotron-3-super-120b-a12b",
    nimApiKey: process.env.NVIDIA_NIM_API_KEY || "",
    githubRepoOwner: process.env.GITHUB_REPO_OWNER || "",
    githubRepoName: process.env.GITHUB_REPO_NAME || "linkedaide",
    githubDispatchPat: process.env.GITHUB_DISPATCH_PAT || "",
    autoRefreshInterval: 600,
    executionMode: "cloud",
    headless: true,
    minimizeToTray: true,
    notificationsEnabled: true,
    maxCommentsPerDay: 15,
    maxPostsPerDay: 3,
    maxConnectionsPerDay: 10,
    maxSuggestionsPerRun: 3,
    actionTtlHours: 12,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
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
    if (updated.timezone !== undefined) {
      updated.timezone = updated.timezone.trim();
    }
    if (Array.isArray(updated.userFocusAreas)) {
      updated.userFocusAreas = updated.userFocusAreas
        .map((s) => (typeof s === "string" ? s.trim() : ""))
        .filter(Boolean);
    }
    if (Array.isArray(updated.targetHashtags)) {
      updated.targetHashtags = updated.targetHashtags
        .map((s) => (typeof s === "string" ? s.trim() : ""))
        .filter(Boolean);
    }
    if (Array.isArray(updated.scoutTargetUrls)) {
      updated.scoutTargetUrls = updated.scoutTargetUrls
        .map((s) => (typeof s === "string" ? s.trim() : ""))
        .filter(Boolean);
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
    async (
      _event,
      credentials?: { workerUrl?: string; apiSecret?: string },
    ) => {
      const result = await workerClient.testConnection({
        baseUrl: credentials?.workerUrl,
        apiSecret: credentials?.apiSecret,
      });
      if (result.success && credentials?.workerUrl && credentials?.apiSecret) {
        if (realtimeClient) {
          realtimeClient.updateCredentials(
            credentials.workerUrl,
            credentials.apiSecret,
          );
        }
      }
      return result;
    },
  );

  ipcMain.handle(
    "api:fetchState",
    async (
      _event,
      credentials?: { workerUrl?: string; apiSecret?: string },
    ) => {
      if (credentials?.workerUrl || credentials?.apiSecret) {
        workerClient.updateConfig({
          baseUrl: credentials.workerUrl,
          apiSecret: credentials.apiSecret,
        });
      }
      return await workerClient.fetchState();
    },
  );

  ipcMain.handle(
    "api:executeAction",
    async (
      _event,
      action: "approve" | "reject",
      itemId: string,
      draftText?: string,
    ) => {
      const settings = loadSettings();
      if (settings.executionMode === "local") {
        const repoRoot = path.resolve(__dirname, "../..");
        if (action === "approve" && draftText) {
          try {
            const pendingFilePath = path.join(
              repoRoot,
              "state/pending",
              `${itemId}.json`,
            );
            if (fs.existsSync(pendingFilePath)) {
              const pendingData = JSON.parse(
                fs.readFileSync(pendingFilePath, "utf-8"),
              );
              pendingData.draft_text = draftText;
              fs.writeFileSync(
                pendingFilePath,
                JSON.stringify(pendingData, null, 2),
                "utf-8",
              );
            }
          } catch (err) {
            console.warn("Failed updating local pending draft file:", err);
          }
        }
        return new Promise<ActionResult>((resolve) => {
          const child = spawn(
            "uv",
            [
              "run",
              "agent",
              "execute",
              "--action",
              action,
              "--item-id",
              itemId,
            ],
            {
              cwd: repoRoot,
              env: {
                ...process.env,
                HEADLESS: String(settings.headless ?? true),
                ...(settings.nimApiKey
                  ? { NVIDIA_NIM_API_KEY: settings.nimApiKey }
                  : {}),
                ...(settings.nimModel
                  ? { NIM_MODEL_PRIMARY: settings.nimModel }
                  : {}),
              },
            },
          );
          child.on("close", (code) => {
            resolve({
              success: code === 0,
              itemId,
              action,
              message:
                code === 0
                  ? "Local execution completed"
                  : "Local execution failed",
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
      return await workerClient.executeAction(
        action,
        itemId,
        {
          repo_owner: settings.githubRepoOwner,
          repo_name: settings.githubRepoName,
          github_pat: settings.githubDispatchPat,
        },
        undefined,
        draftText,
      );
    },
  );

  ipcMain.handle(
    "api:executeConnectionAction",
    async (_event, action: "approve" | "reject", id: string, note?: string) => {
      const settings = loadSettings();
      if (settings.executionMode === "local") {
        const repoRoot = path.resolve(__dirname, "../..");
        if (note) {
          try {
            const queuePath = path.join(
              repoRoot,
              "state/connection_queue.json",
            );
            if (fs.existsSync(queuePath)) {
              const queue = JSON.parse(fs.readFileSync(queuePath, "utf-8"));
              if (Array.isArray(queue)) {
                const idx = queue.findIndex((c: any) => c.id === id);
                if (idx >= 0) {
                  queue[idx].note_text = note;
                  if (action === "approve") {
                    queue[idx].status = "approved";
                    queue[idx].approved_at = new Date().toISOString();
                  } else {
                    queue[idx].status = "rejected";
                  }
                  fs.writeFileSync(
                    queuePath,
                    JSON.stringify(queue, null, 2),
                    "utf-8",
                  );
                }
              }
            }
          } catch (err) {
            console.warn("Failed updating local connection queue file:", err);
          }
        }
        return new Promise<ActionResult>((resolve) => {
          const child = spawn(
            "uv",
            ["run", "agent", "execute", "--action", action, "--item-id", id],
            {
              cwd: repoRoot,
              env: {
                ...process.env,
                HEADLESS: String(settings.headless ?? true),
                ...(settings.nimApiKey
                  ? { NVIDIA_NIM_API_KEY: settings.nimApiKey }
                  : {}),
                ...(settings.nimModel
                  ? { NIM_MODEL_PRIMARY: settings.nimModel }
                  : {}),
              },
            },
          );
          child.on("close", (code) => {
            resolve({
              success: code === 0,
              itemId: id,
              action,
              message:
                code === 0
                  ? "Local execution completed"
                  : "Local execution failed",
            });
          });
          child.on("error", (err) => {
            resolve({
              success: false,
              itemId: id,
              action,
              error: err.message,
            });
          });
        });
      }
      return await workerClient.executeAction(
        action,
        id,
        {
          repo_owner: settings.githubRepoOwner,
          repo_name: settings.githubRepoName,
          github_pat: settings.githubDispatchPat,
        },
        note,
      );
    },
  );

  ipcMain.handle("api:triggerScout", async () => {
    const settings = loadSettings();
    if (settings.executionMode === "local") {
      return new Promise<boolean>((resolve) => {
        const repoRoot = path.resolve(__dirname, "../..");
        const scoutArgs = ["run", "agent", "scout"];
        if (settings.headless === false) {
          scoutArgs.push("--headed");
        }
        const child = spawn("uv", scoutArgs, {
          cwd: repoRoot,
          env: {
            ...process.env,
            HEADLESS: String(settings.headless ?? true),
            ...(settings.nimApiKey
              ? { NVIDIA_NIM_API_KEY: settings.nimApiKey }
              : {}),
            ...(settings.nimModel
              ? { NIM_MODEL_PRIMARY: settings.nimModel }
              : {}),
            ...(settings.userFocusAreas?.length
              ? { USER_FOCUS_AREAS: JSON.stringify(settings.userFocusAreas) }
              : {}),
            ...(settings.targetHashtags?.length
              ? { TARGET_HASHTAGS: JSON.stringify(settings.targetHashtags) }
              : {}),
            ...(settings.scoutTargetUrls?.length
              ? { SCOUT_TARGET_URLS: JSON.stringify(settings.scoutTargetUrls) }
              : {}),
            ...(settings.feedScrollScreens
              ? { SCOUT_SCROLL_SCREENS: String(settings.feedScrollScreens) }
              : {}),
            ...(settings.candidatePoolMultiplier
              ? {
                  CANDIDATE_POOL_MULTIPLIER: String(
                    settings.candidatePoolMultiplier,
                  ),
                }
              : {}),
            ...(settings.minTriageConfidence !== undefined
              ? { MIN_TRIAGE_CONFIDENCE: String(settings.minTriageConfidence) }
              : {}),
            ...(settings.maxCommentWords
              ? { MAX_COMMENT_WORDS: String(settings.maxCommentWords) }
              : {}),
            ...(settings.enablePreCommentReaction !== undefined
              ? {
                  ENABLE_PRE_COMMENT_REACTION: String(
                    settings.enablePreCommentReaction,
                  ),
                }
              : {}),
            ...(settings.defaultReactionType
              ? { DEFAULT_REACTION_TYPE: settings.defaultReactionType }
              : {}),
            ...(settings.maxSuggestionsPerRun
              ? {
                  MAX_SUGGESTIONS_PER_RUN: String(
                    settings.maxSuggestionsPerRun,
                  ),
                }
              : {}),
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

  ipcMain.handle("api:triggerIdeate", async () => {
    const settings = loadSettings();
    if (settings.executionMode === "local") {
      return new Promise<boolean>((resolve) => {
        const repoRoot = path.resolve(__dirname, "../..");
        const ideateArgs = ["run", "agent", "ideate"];
        const child = spawn("uv", ideateArgs, {
          cwd: repoRoot,
          env: {
            ...process.env,
            ...(settings.nimApiKey
              ? { NVIDIA_NIM_API_KEY: settings.nimApiKey }
              : {}),
            ...(settings.nimModel
              ? { NIM_MODEL_PRIMARY: settings.nimModel }
              : {}),
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
    return await workerClient.triggerIdeate({
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
    },
  );

  ipcMain.handle("api:saveSession", async (_event, sessionData: string) => {
    return await workerClient.saveSession(sessionData);
  });

  ipcMain.handle("api:fetchScheduledPosts", async () => {
    return await workerClient.fetchScheduledPosts();
  });

  ipcMain.handle("api:saveScheduledPost", async (_event, post: any) => {
    return await workerClient.saveScheduledPost(post);
  });

  ipcMain.handle("api:deleteScheduledPost", async (_event, id: string) => {
    return await workerClient.deleteScheduledPost(id);
  });

  ipcMain.handle("api:fetchScoutSchedule", async () => {
    return await workerClient.fetchScoutSchedule();
  });

  ipcMain.handle("api:saveScoutSchedule", async (_event, schedule: any) => {
    return await workerClient.saveScoutSchedule(schedule);
  });

  ipcMain.handle("api:fetchConnectionQueue", async () => {
    return await workerClient.fetchConnectionQueue();
  });

  ipcMain.handle(
    "api:checkForkSync",
    async (_event, owner?: string, repo?: string, pat?: string) => {
      const settings = loadSettings();
      const targetOwner = (owner || settings.githubRepoOwner || "").trim();
      const targetRepo = (
        repo ||
        settings.githubRepoName ||
        "linkedaide"
      ).trim();
      const targetPat = (pat || settings.githubDispatchPat || "").trim();

      if (!targetOwner || targetOwner.toLowerCase() === "mahdi-behnam") {
        return { isFork: false, behindBy: 0, aheadBy: 0, status: "identical" };
      }

      try {
        const headers: Record<string, string> = {
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "LinkedAide-Desktop",
        };
        if (targetPat) {
          headers["Authorization"] = `Bearer ${targetPat}`;
        }

        const url = `https://api.github.com/repos/${targetOwner}/${targetRepo}/compare/main...mahdi-behnam:main`;
        const resp = await fetch(url, { headers });
        if (!resp.ok) {
          return {
            isFork: true,
            behindBy: 0,
            aheadBy: 0,
            status: "unknown",
            error: `HTTP ${resp.status}`,
          };
        }
        const data = (await resp.json()) as {
          status?: string;
          behind_by?: number;
          ahead_by?: number;
        };
        return {
          isFork: true,
          behindBy: data.behind_by ?? 0,
          aheadBy: data.ahead_by ?? 0,
          status: data.status ?? "identical",
        };
      } catch (err: unknown) {
        const error = err instanceof Error ? err.message : String(err);
        return {
          isFork: true,
          behindBy: 0,
          aheadBy: 0,
          status: "error",
          error,
        };
      }
    },
  );

  // Local Settings Handlers
  ipcMain.handle("settings:get", async () => {
    return loadSettings();
  });

  ipcMain.handle(
    "settings:save",
    async (_event, settings: Partial<DesktopSettings>) => {
      return saveSettings(settings);
    },
  );

  // Fernet Cryptography Handlers
  ipcMain.handle(
    "crypto:encryptSession",
    async (_event, data: string, base64Key: string) => {
      return encryptSession(data, base64Key);
    },
  );

  ipcMain.handle(
    "crypto:decryptSession",
    async (_event, token: string, base64Key: string) => {
      return decryptSession(token, base64Key);
    },
  );

  ipcMain.handle("crypto:generateFernetKey", async () => {
    return generateFernetKey();
  });

  // LinkedIn Auth Handlers
  ipcMain.handle("auth:captureSession", async () => {
    const settings = loadSettings();
    if (!settings.encryptionKey) {
      return {
        success: false,
        error: "Session encryption key not configured in settings",
      };
    }
    const targetWin =
      mainWindow ||
      BrowserWindow.getFocusedWindow() ||
      BrowserWindow.getAllWindows()[0];
    return await captureLinkedInSession(
      targetWin,
      settings.encryptionKey,
      async (data: string) => {
        return await workerClient.saveSession(data);
      },
    );
  });

  ipcMain.handle("auth:checkSessionHealth", async () => {
    try {
      const cookies = await session.defaultSession.cookies.get({
        name: "li_at",
      });
      const liAt = cookies.find(
        (c) => c.domain?.includes("linkedin.com") || c.name === "li_at",
      );
      if (liAt && liAt.value) {
        let daysRemaining = 18;
        if (typeof liAt.expirationDate === "number") {
          const days = Math.round(
            (liAt.expirationDate * 1000 - Date.now()) / (1000 * 60 * 60 * 24),
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

    return {
      valid: false,
      daysRemaining: 0,
      details: "No active LinkedIn session found in storage",
    };
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

      const response = await fetch(
        "https://integrate.api.nvidia.com/v1/models",
        {
          method: "GET",
          headers,
        },
      );

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

  // Media Upload Handler (Cloudflare R2 Media Vault / Local Storage)
  ipcMain.handle(
    "api:uploadMedia",
    async (
      _event,
      fileName: string,
      fileBuffer: ArrayBuffer,
      contentType?: string,
    ) => {
      try {
        const settings = loadSettings();
        const ext =
          path.extname(fileName) ||
          (contentType?.includes("pdf") ? ".pdf" : ".png");
        const uniqueKey = `posts/${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 7)}${ext}`;

        if (workerClient && settings.workerUrl && settings.apiSecret) {
          return await workerClient.uploadMedia(
            uniqueKey,
            fileBuffer,
            contentType,
          );
        }

        // Local storage fallback under userData/media
        const mediaDir = path.join(app.getPath("userData"), "media");
        if (!fs.existsSync(mediaDir)) {
          fs.mkdirSync(mediaDir, { recursive: true });
        }
        const localFilePath = path.join(mediaDir, path.basename(uniqueKey));
        fs.writeFileSync(localFilePath, Buffer.from(fileBuffer));
        return {
          success: true,
          key: uniqueKey,
          url: `file://${localFilePath}`,
        };
      } catch (err: unknown) {
        const error = err instanceof Error ? err.message : String(err);
        return { success: false, error };
      }
    },
  );

  // CLI Doctor Execution Handler (uv run agent doctor)
  ipcMain.handle("doctor:runCliDoctor", async () => {
    return new Promise<{ success: boolean; exitCode: number; output: string }>(
      (resolve) => {
        try {
          const repoRoot = path.resolve(__dirname, "../..");
          const settings = loadSettings();
          const child = spawn(
            "uv",
            ["run", "agent", "doctor", "--repo-root", repoRoot],
            {
              cwd: repoRoot,
              env: {
                ...process.env,
                ...(settings.nimApiKey
                  ? { NVIDIA_NIM_API_KEY: settings.nimApiKey }
                  : {}),
                ...(settings.nimModel
                  ? { NIM_MODEL_PRIMARY: settings.nimModel }
                  : {}),
              },
            },
          );

          let output = "";
          child.stdout?.on("data", (data) => {
            output += data.toString();
          });
          child.stderr?.on("data", (data) => {
            output += data.toString();
          });

          child.on("close", (code) => {
            resolve({
              success: code === 0,
              exitCode: code ?? 0,
              output: output.trim(),
            });
          });

          child.on("error", (err) => {
            resolve({
              success: false,
              exitCode: 1,
              output: `Failed to spawn CLI doctor: ${err.message}`,
            });
          });
        } catch (err: unknown) {
          const error = err instanceof Error ? err.message : String(err);
          resolve({
            success: false,
            exitCode: 1,
            output: `Error executing doctor check: ${error}`,
          });
        }
      },
    );
  });

  // Window Management & Custom Title Bar Handlers
  ipcMain.handle("window:minimize", () => {
    const targetWin = mainWindow || BrowserWindow.getFocusedWindow();
    if (targetWin && !targetWin.isDestroyed()) {
      targetWin.minimize();
      return true;
    }
    return false;
  });

  ipcMain.handle("window:maximize", () => {
    const targetWin = mainWindow || BrowserWindow.getFocusedWindow();
    if (targetWin && !targetWin.isDestroyed()) {
      if (targetWin.isMaximized()) {
        targetWin.unmaximize();
      } else {
        targetWin.maximize();
      }
      return true;
    }
    return false;
  });

  ipcMain.handle("window:close", () => {
    const targetWin = mainWindow || BrowserWindow.getFocusedWindow();
    if (targetWin && !targetWin.isDestroyed()) {
      targetWin.close();
      return true;
    }
    return false;
  });

  ipcMain.handle("window:isMaximized", () => {
    const targetWin = mainWindow || BrowserWindow.getFocusedWindow();
    if (targetWin && !targetWin.isDestroyed()) {
      return targetWin.isMaximized();
    }
    return false;
  });

  ipcMain.handle(
    "window:setTitleBarTheme",
    (_event, theme: "dark" | "light") => {
      const targetWin = mainWindow || BrowserWindow.getFocusedWindow();
      if (
        targetWin &&
        !targetWin.isDestroyed() &&
        process.platform !== "darwin" &&
        typeof targetWin.setTitleBarOverlay === "function"
      ) {
        try {
          targetWin.setTitleBarOverlay({
            color: theme === "dark" ? "#222222" : "#f2f2f7",
            symbolColor: theme === "dark" ? "#98989d" : "#86868b",
            height: 44,
          });
          return true;
        } catch (err) {
          console.warn("Failed to set title bar overlay theme:", err);
          return false;
        }
      }
      return false;
    },
  );
}

function getAppIconPath(): string | undefined {
  const isWin = process.platform === "win32";
  const primaryExt = isWin ? "ico" : "png";
  const fallbackExt = isWin ? "png" : "ico";

  const candidateFileNames = [
    `icon.${primaryExt}`,
    `icon.${fallbackExt}`,
    "favicon.ico",
    "app-icon.png",
  ];

  const candidateDirs = [
    // Production / packaged asar paths (inside dist, build, or public relative to dist-electron)
    path.join(__dirname, "../build"),
    path.join(__dirname, "../dist"),
    path.join(__dirname, "../public"),
    // Development directories relative to process.cwd()
    path.join(process.cwd(), "desktop/build"),
    path.join(process.cwd(), "desktop/dist"),
    path.join(process.cwd(), "desktop/public"),
    path.join(process.cwd(), "build"),
    path.join(process.cwd(), "dist"),
    path.join(process.cwd(), "public"),
    path.join(process.cwd(), "assets"),
  ];

  for (const fileName of candidateFileNames) {
    for (const dir of candidateDirs) {
      const fullPath = path.join(dir, fileName);
      if (fs.existsSync(fullPath)) {
        return fullPath;
      }
    }
  }

  return undefined;
}

function createWindow(): BrowserWindow {
  const iconPath = getAppIconPath();
  const isMac = process.platform === "darwin";

  const win = new BrowserWindow({
    title: "LinkedAide",
    ...(iconPath ? { icon: iconPath } : {}),
    width: 1280,
    height: 820,
    minWidth: 1000,
    minHeight: 650,
    backgroundColor: "#09090b",
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: "hidden",
    ...(isMac
      ? {
          trafficLightPosition: { x: 16, y: 14 },
        }
      : {
          titleBarOverlay: {
            color: "#222222",
            symbolColor: "#98989d",
            height: 44,
          },
        }),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http:") || url.startsWith("https:")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  if (iconPath && typeof win.setIcon === "function") {
    try {
      win.setIcon(iconPath);
    } catch (err) {
      console.warn("Failed setting window icon explicitly:", err);
    }
  }

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
      !fs.existsSync(path.join(__dirname, "../dist/index.html")),
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

  setupAppMenu({
    getMainWindow: () => mainWindow,
    workerClient,
    workerUrl: settings.workerUrl,
    onCheckForUpdates: () =>
      updateManager?.checkForUpdates() ?? Promise.resolve(false),
  });

  registerIpcHandlers();
  mainWindow = createWindow();

  trayManager = new TrayManager(mainWindow, workerClient);
  pollingEngine = new PollingEngine({
    workerClient,
    trayManager,
    mainWindow,
    intervalMs: (settings.autoRefreshInterval || 600) * 1000,
  });
  pollingEngine.start(true);

  realtimeClient = new RealtimePushClient(
    mainWindow,
    settings.workerUrl,
    settings.apiSecret,
  );
  realtimeClient.connect();

  updateManager = new UpdateManager({ mainWindow });
  updateManager.checkForUpdates().catch((err) => {
    console.warn("Startup update check failed:", err);
  });

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
      if (updateManager) {
        updateManager.setMainWindow(mainWindow);
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
  if (updateManager) {
    updateManager.destroy();
    updateManager = null;
  }
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
