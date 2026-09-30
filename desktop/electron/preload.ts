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
} from "./types";

const api: ElectronAPI = {
  fetchState: (): Promise<AgentState> => ipcRenderer.invoke("api:fetchState"),

  executeAction: (
    action: "approve" | "reject",
    itemId: string
  ): Promise<ActionResult> =>
    ipcRenderer.invoke("api:executeAction", action, itemId),

  triggerScout: (): Promise<boolean> => ipcRenderer.invoke("api:triggerScout"),

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

  onRealtimeEvent: (callback: (event: any) => void): (() => void) => {
    const subscription = (_event: Electron.IpcRendererEvent, payload: any) => {
      callback(payload);
    };
    ipcRenderer.on("realtime:event", subscription);
    return () => {
      ipcRenderer.removeListener("realtime:event", subscription);
    };
  },
};

contextBridge.exposeInMainWorld("api", api);
