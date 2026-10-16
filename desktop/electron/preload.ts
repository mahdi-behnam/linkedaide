/**
 * Secure Preload Bridge
 *
 * Exposes a minimal, hardened `window.api` interface to the renderer
 * process via Electron contextBridge with contextIsolation.
 */

import { contextBridge, ipcRenderer } from "electron";
import type {
  ActionResult,
  AgentState,
  DesktopSettings,
  ElectronAPI,
  ScheduledPost,
  ConnectionRequestAction,
  AutomatedCommentWindow,
  UpdateState,
  ForkSyncResult,
} from "./types";

const api: ElectronAPI = {
  fetchState: (
    credentials?: { workerUrl?: string; apiSecret?: string }
  ): Promise<AgentState> => ipcRenderer.invoke("api:fetchState", credentials),

  testConnection: (
    credentials?: { workerUrl?: string; apiSecret?: string }
  ): Promise<{ success: boolean; latencyMs?: number; error?: string }> =>
    ipcRenderer.invoke("api:testConnection", credentials),

  executeAction: (
    action: "approve" | "reject",
    itemId: string,
    draftText?: string
  ): Promise<ActionResult> =>
    ipcRenderer.invoke("api:executeAction", action, itemId, draftText),

  executeConnectionAction: (
    action: "approve" | "reject",
    id: string,
    note?: string
  ): Promise<ActionResult> =>
    ipcRenderer.invoke("api:executeConnectionAction", action, id, note),

  triggerScout: (): Promise<boolean> => ipcRenderer.invoke("api:triggerScout"),
  triggerIdeate: (): Promise<boolean> => ipcRenderer.invoke("api:triggerIdeate"),

  togglePause: (paused: boolean): Promise<boolean> =>
    ipcRenderer.invoke("api:togglePause", paused),

  clearIncident: (): Promise<boolean> =>
    ipcRenderer.invoke("api:clearIncident"),

  rewriteDraft: (draftText: string, tone: string): Promise<string> =>
    ipcRenderer.invoke("api:rewriteDraft", draftText, tone),

  saveSession: (sessionData: string): Promise<boolean> =>
    ipcRenderer.invoke("api:saveSession", sessionData),

  getSettings: (): Promise<DesktopSettings> =>
    ipcRenderer.invoke("settings:get"),

  saveSettings: (settings: Partial<DesktopSettings>): Promise<boolean> =>
    ipcRenderer.invoke("settings:save", settings),

  encryptSession: (data: string, base64Key: string): Promise<string> =>
    ipcRenderer.invoke("crypto:encryptSession", data, base64Key),

  decryptSession: (token: string, base64Key: string): Promise<string> =>
    ipcRenderer.invoke("crypto:decryptSession", token, base64Key),

  generateFernetKey: (): Promise<string> =>
    ipcRenderer.invoke("crypto:generateFernetKey"),

  captureSession: (): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke("auth:captureSession"),

  checkSessionHealth: (): Promise<{ valid: boolean; daysRemaining?: number; details?: string }> =>
    ipcRenderer.invoke("auth:checkSessionHealth"),

  fetchNimModels: (
    apiKey?: string
  ): Promise<{ success: boolean; models: string[]; error?: string }> =>
    ipcRenderer.invoke("llm:fetchNimModels", apiKey),

  onRealtimeEvent: (callback: (event: any) => void): (() => void) => {
    const subscription = (_event: Electron.IpcRendererEvent, payload: any) => {
      callback(payload);
    };
    ipcRenderer.on("realtime:event", subscription);
    return () => {
      ipcRenderer.removeListener("realtime:event", subscription);
    };
  },

  onMenuAction: (callback: (action: string, data?: any) => void): (() => void) => {
    const subscription = (_event: Electron.IpcRendererEvent, action: string, data?: any) => {
      callback(action, data);
    };
    ipcRenderer.on("menu:action", subscription);
    return () => {
      ipcRenderer.removeListener("menu:action", subscription);
    };
  },

  fetchScheduledPosts: (): Promise<ScheduledPost[]> =>
    ipcRenderer.invoke("api:fetchScheduledPosts"),

  saveScheduledPost: (post: ScheduledPost): Promise<ScheduledPost> =>
    ipcRenderer.invoke("api:saveScheduledPost", post),

  deleteScheduledPost: (id: string): Promise<boolean> =>
    ipcRenderer.invoke("api:deleteScheduledPost", id),

  fetchScoutSchedule: (): Promise<AutomatedCommentWindow[]> =>
    ipcRenderer.invoke("api:fetchScoutSchedule"),

  saveScoutSchedule: (schedule: AutomatedCommentWindow[]): Promise<boolean> =>
    ipcRenderer.invoke("api:saveScoutSchedule", schedule),

  fetchConnectionQueue: (): Promise<ConnectionRequestAction[]> =>
    ipcRenderer.invoke("api:fetchConnectionQueue"),

  uploadMedia: (
    fileName: string,
    fileBuffer: ArrayBuffer,
    contentType?: string
  ): Promise<{ success: boolean; key?: string; url?: string; error?: string }> =>
    ipcRenderer.invoke("api:uploadMedia", fileName, fileBuffer, contentType),

  runCliDoctor: (): Promise<{ success: boolean; exitCode: number; output: string }> =>
    ipcRenderer.invoke("doctor:runCliDoctor"),

  platform: process.platform,

  minimizeWindow: (): Promise<boolean> =>
    ipcRenderer.invoke("window:minimize"),

  maximizeWindow: (): Promise<boolean> =>
    ipcRenderer.invoke("window:maximize"),

  closeWindow: (): Promise<boolean> =>
    ipcRenderer.invoke("window:close"),

  isMaximized: (): Promise<boolean> =>
    ipcRenderer.invoke("window:isMaximized"),

  setTitleBarTheme: (theme: "dark" | "light"): Promise<boolean> =>
    ipcRenderer.invoke("window:setTitleBarTheme", theme),

  updaterCheckForUpdates: (): Promise<boolean> =>
    ipcRenderer.invoke("updater:checkForUpdates"),

  updaterStartDownload: (): Promise<boolean> =>
    ipcRenderer.invoke("updater:startDownload"),

  updaterCancelDownload: (): Promise<boolean> =>
    ipcRenderer.invoke("updater:cancelDownload"),

  updaterQuitAndInstall: (): Promise<boolean> =>
    ipcRenderer.invoke("updater:quitAndInstall"),

  updaterGetStatus: (): Promise<UpdateState> =>
    ipcRenderer.invoke("updater:getStatus"),

  onUpdaterEvent: (callback: (state: UpdateState) => void): (() => void) => {
    const subscription = (
      _event: Electron.IpcRendererEvent,
      payload: UpdateState,
    ) => {
      callback(payload);
    };
    ipcRenderer.on("updater:event", subscription);
    return () => {
      ipcRenderer.removeListener("updater:event", subscription);
    };
  },

  checkForkSync: (
    owner?: string,
    repo?: string,
    pat?: string,
  ): Promise<ForkSyncResult> =>
    ipcRenderer.invoke("api:checkForkSync", owner, repo, pat),
};

contextBridge.exposeInMainWorld("api", api);
