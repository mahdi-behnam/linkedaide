/**
 * Application Menu Builder
 *
 * Configures the native desktop menu bar (File, Edit, Agent, View, Window, Help)
 * tailored specifically for LinkedIn Human-in-the-Loop Agent.
 */

import { Menu, MenuItemConstructorOptions, shell } from "electron";
import { AppMenuOptions } from "./types";
import {
  clearIncidentAction,
  navigateToTab,
  sendMenuAction,
  showAboutDialog,
  togglePauseAction,
  triggerScoutAction,
} from "./actions";

export function buildAppMenuTemplate(
  options: AppMenuOptions,
): MenuItemConstructorOptions[] {
  const isMac = process.platform === "darwin";
  const getWin = options.getMainWindow;
  const template: MenuItemConstructorOptions[] = [];

  // 1. macOS Application Menu
  if (isMac) {
    template.push({
      label: "LinkedAide",
      submenu: [
        {
          label: "About LinkedAide",
          click: () => showAboutDialog(getWin),
        },
        { type: "separator" },
        {
          label: "Preferences...",
          accelerator: "CmdOrCtrl+,",
          click: () => navigateToTab(getWin, "settings"),
        },
        { type: "separator" },
        { role: "services" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    });
  }

  // 2. File Menu
  const fileSubmenu: MenuItemConstructorOptions[] = [
    {
      label: "New Post Draft",
      accelerator: "CmdOrCtrl+N",
      click: () => navigateToTab(getWin, "composer"),
    },
    {
      label: "Trigger Feed Scout",
      accelerator: "CmdOrCtrl+Shift+S",
      click: () => triggerScoutAction(options),
    },
    {
      label: "Sync KV Edge State",
      accelerator: "CmdOrCtrl+R",
      click: () => sendMenuAction(getWin, "refresh-state"),
    },
    { type: "separator" },
    {
      label: "Connect LinkedIn Account...",
      accelerator: "CmdOrCtrl+Shift+L",
      click: () => navigateToTab(getWin, "vault"),
    },
    {
      label: "Audit History Log",
      accelerator: "CmdOrCtrl+Shift+H",
      click: () => navigateToTab(getWin, "history"),
    },
    { type: "separator" },
  ];

  if (!isMac) {
    fileSubmenu.push(
      {
        label: "Settings",
        accelerator: "Ctrl+,",
        click: () => navigateToTab(getWin, "settings"),
      },
      { type: "separator" },
      { role: "quit", label: "Exit", accelerator: "Ctrl+Q" },
    );
  } else {
    fileSubmenu.push({ role: "close" });
  }

  template.push({
    label: "File",
    submenu: fileSubmenu,
  });

  // 3. Edit Menu
  template.push({
    label: "Edit",
    submenu: [
      { role: "undo" },
      { role: "redo" },
      { type: "separator" },
      { role: "cut" },
      { role: "copy" },
      { role: "paste" },
      { role: "pasteAndMatchStyle" },
      { role: "delete" },
      { role: "selectAll" },
      { type: "separator" },
      {
        label: "Quick Search",
        accelerator: "CmdOrCtrl+K",
        click: () => sendMenuAction(getWin, "focus-search"),
      },
    ],
  });

  // 4. Agent Menu (HITL Autonomous Operations)
  template.push({
    label: "Agent",
    submenu: [
      {
        label: "Trigger Scout Now",
        accelerator: "CmdOrCtrl+Shift+S",
        click: () => triggerScoutAction(options),
      },
      {
        label: "Pause / Resume Agent",
        accelerator: "Alt+P",
        click: () => togglePauseAction(options),
      },
      {
        label: "Reset Circuit Breaker",
        click: () => clearIncidentAction(options),
      },
      { type: "separator" },
      {
        label: "Review Approval Queue",
        accelerator: "CmdOrCtrl+Shift+Q",
        click: () => navigateToTab(getWin, "queue"),
      },
      {
        label: "Review Outreach Queue",
        accelerator: "CmdOrCtrl+Shift+O",
        click: () => navigateToTab(getWin, "outreach"),
      },
      { type: "separator" },
      {
        label: "Run System Diagnostics",
        accelerator: "CmdOrCtrl+Shift+D",
        click: () => sendMenuAction(getWin, "run-doctor"),
      },
    ],
  });

  // 5. View Menu
  template.push({
    label: "View",
    submenu: [
      {
        label: "Navigation",
        submenu: [
          {
            label: "Dashboard",
            accelerator: "CmdOrCtrl+1",
            click: () => navigateToTab(getWin, "dashboard"),
          },
          {
            label: "Approval Queue",
            accelerator: "CmdOrCtrl+2",
            click: () => navigateToTab(getWin, "queue"),
          },
          {
            label: "Outreach Queue",
            accelerator: "CmdOrCtrl+3",
            click: () => navigateToTab(getWin, "outreach"),
          },
          {
            label: "Post Composer",
            accelerator: "CmdOrCtrl+4",
            click: () => navigateToTab(getWin, "composer"),
          },
          {
            label: "Content Calendar",
            accelerator: "CmdOrCtrl+5",
            click: () => navigateToTab(getWin, "calendar"),
          },
          {
            label: "Growth Analytics",
            accelerator: "CmdOrCtrl+6",
            click: () => navigateToTab(getWin, "analytics"),
          },
          {
            label: "LinkedIn Vault",
            accelerator: "CmdOrCtrl+7",
            click: () => navigateToTab(getWin, "vault"),
          },
          {
            label: "Audit History",
            accelerator: "CmdOrCtrl+8",
            click: () => navigateToTab(getWin, "history"),
          },
          {
            label: "System Doctor",
            accelerator: "CmdOrCtrl+9",
            click: () => navigateToTab(getWin, "doctor"),
          },
          {
            label: "Settings",
            accelerator: "CmdOrCtrl+0",
            click: () => navigateToTab(getWin, "settings"),
          },
        ],
      },
      { type: "separator" },
      {
        label: "Toggle Dark / Light Theme",
        accelerator: "CmdOrCtrl+Shift+T",
        click: () => sendMenuAction(getWin, "toggle-theme"),
      },
      {
        label: "Toggle Sidebar",
        accelerator: "CmdOrCtrl+B",
        click: () => sendMenuAction(getWin, "toggle-sidebar"),
      },
      { type: "separator" },
      { role: "reload" },
      { role: "forceReload" },
      { role: "toggleDevTools" },
      { type: "separator" },
      { role: "resetZoom" },
      { role: "zoomIn" },
      { role: "zoomOut" },
      { type: "separator" },
      { role: "togglefullscreen" },
    ],
  });

  // 6. Window Menu
  const windowSubmenu: MenuItemConstructorOptions[] = [
    { role: "minimize" },
    { role: "zoom" },
  ];
  if (isMac) {
    windowSubmenu.push(
      { type: "separator" },
      { role: "front" },
      { type: "separator" },
      { role: "window" },
    );
  } else {
    windowSubmenu.push({ role: "close" });
  }

  template.push({
    label: "Window",
    submenu: windowSubmenu,
  });

  // 7. Help Menu
  template.push({
    label: "Help",
    submenu: [
      {
        label: "Keyboard Shortcuts Cheatsheet",
        accelerator: "CmdOrCtrl+/",
        click: () => sendMenuAction(getWin, "open-shortcuts"),
      },
      {
        label: "System Health Diagnostics",
        click: () => navigateToTab(getWin, "doctor"),
      },
      { type: "separator" },
      {
        label: "Documentation & Setup Guide",
        click: () => {
          shell.openExternal(
            "https://github.com/mahdi-behnam/linkedaide#readme",
          );
        },
      },
      {
        label: "Cloudflare Relay Health",
        click: () => {
          const workerUrl =
            options.workerUrl || "https://relay.linkedaide.workers.dev";
          shell.openExternal(`${workerUrl}/health`);
        },
      },
      { type: "separator" },
      {
        label: "About LinkedAide",
        click: () => showAboutDialog(getWin),
      },
    ],
  });

  return template;
}

export function createAppMenu(options: AppMenuOptions): Menu {
  const template = buildAppMenuTemplate(options);
  return Menu.buildFromTemplate(template);
}

export function setupAppMenu(options: AppMenuOptions): Menu {
  const menu = createAppMenu(options);
  Menu.setApplicationMenu(menu);
  return menu;
}
