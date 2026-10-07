/**
 * Handlers and dispatchers for native application menu actions.
 */

import { BrowserWindow, dialog } from "electron";
import { NavigationTab } from "../types";
import { AppMenuOptions, MenuAction } from "./types";

export function sendMenuAction(
  winOrGetter: BrowserWindow | (() => BrowserWindow | null) | null,
  action: MenuAction,
  data?: unknown
): void {
  const win = typeof winOrGetter === "function" ? winOrGetter() : winOrGetter;
  const targetWin = win || BrowserWindow.getFocusedWindow() || null;
  if (targetWin && !targetWin.isDestroyed()) {
    targetWin.webContents.send("menu:action", action, data);
  }
}

export function navigateToTab(
  winOrGetter: BrowserWindow | (() => BrowserWindow | null) | null,
  tab: NavigationTab
): void {
  sendMenuAction(winOrGetter, "navigate", tab);
}

export async function triggerScoutAction(options: AppMenuOptions): Promise<void> {
  const win = options.getMainWindow();
  sendMenuAction(win, "trigger-scout");
  if (options.onTriggerScout) {
    try {
      await options.onTriggerScout();
    } catch (err) {
      console.error("AppMenu: failed to execute onTriggerScout callback:", err);
    }
  } else if (options.workerClient) {
    try {
      await options.workerClient.triggerScout();
    } catch (err) {
      console.error("AppMenu: failed to trigger scout via workerClient:", err);
    }
  }
}

export async function togglePauseAction(options: AppMenuOptions): Promise<void> {
  const win = options.getMainWindow();
  sendMenuAction(win, "toggle-pause");
  if (options.onTogglePause) {
    const nextState = options.isPaused ? !options.isPaused() : true;
    try {
      await options.onTogglePause(nextState);
    } catch (err) {
      console.error("AppMenu: failed to toggle pause callback:", err);
    }
  } else if (options.workerClient) {
    const nextState = options.isPaused ? !options.isPaused() : true;
    try {
      await options.workerClient.togglePause(nextState);
    } catch (err) {
      console.error("AppMenu: failed to toggle pause via workerClient:", err);
    }
  }
}

export async function clearIncidentAction(options: AppMenuOptions): Promise<void> {
  const win = options.getMainWindow();
  sendMenuAction(win, "clear-incident");
  if (options.onClearIncident) {
    try {
      await options.onClearIncident();
    } catch (err) {
      console.error("AppMenu: failed to clear incident callback:", err);
    }
  } else if (options.workerClient) {
    try {
      await options.workerClient.clearIncident();
    } catch (err) {
      console.error("AppMenu: failed to clear incident via workerClient:", err);
    }
  }
}

export function showAboutDialog(
  winOrGetter: BrowserWindow | (() => BrowserWindow | null) | null
): void {
  const win = typeof winOrGetter === "function" ? winOrGetter() : winOrGetter;
  const targetWin = win || BrowserWindow.getFocusedWindow() || null;

  const dialogOptions = {
    type: "info" as const,
    title: "About LinkedAide",
    message: "LinkedAide",
    detail:
      "Version: 1.0.0\nHuman-in-the-Loop LinkedIn Autonomous Agent\n" +
      "Deterministic safety with mandatory human approval via Telegram & Desktop.\n\n" +
      "Powered by NVIDIA NIM, Playwright & Cloudflare Workers KV.",
    buttons: ["OK"],
  };

  if (targetWin && !targetWin.isDestroyed()) {
    dialog.showMessageBox(targetWin, dialogOptions);
  } else {
    dialog.showMessageBox(dialogOptions);
  }
}
