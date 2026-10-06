/**
 * Types and interfaces for the Desktop Native Application Menu.
 */

import { BrowserWindow } from "electron";
export type { NavigationTab } from "../types";
import { WorkerClient } from "../api/workerClient";

export type MenuAction =
  | "navigate"
  | "trigger-scout"
  | "toggle-pause"
  | "clear-incident"
  | "refresh-state"
  | "focus-search"
  | "toggle-theme"
  | "toggle-sidebar"
  | "run-doctor"
  | "open-shortcuts";

export interface AppMenuOptions {
  getMainWindow: () => BrowserWindow | null;
  workerClient?: WorkerClient | null;
  workerUrl?: string;
  isPaused?: () => boolean;
  onTriggerScout?: () => Promise<void>;
  onTogglePause?: (nextState: boolean) => Promise<void>;
  onClearIncident?: () => Promise<void>;
}
