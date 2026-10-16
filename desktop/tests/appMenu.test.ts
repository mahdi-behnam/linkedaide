import { describe, expect, it, vi, beforeEach } from "vitest";
import { Menu, BrowserWindow } from "electron";
import {
  buildAppMenuTemplate,
  createAppMenu,
  setupAppMenu,
  sendMenuAction,
  navigateToTab,
  triggerScoutAction,
  togglePauseAction,
  clearIncidentAction,
} from "../electron/menu";

const mocks = vi.hoisted(() => {
  const mockWebContents = {
    send: vi.fn(),
    isDestroyed: vi.fn().mockReturnValue(false),
  };

  const mockBrowserWindow = {
    show: vi.fn(),
    focus: vi.fn(),
    isDestroyed: vi.fn().mockReturnValue(false),
    webContents: mockWebContents,
  };

  return {
    mockBrowserWindow,
    mockWebContents,
  };
});

vi.mock("electron", () => {
  return {
    app: {
      quit: vi.fn(),
    },
    BrowserWindow: {
      getFocusedWindow: vi.fn(() => mocks.mockBrowserWindow),
    },
    Menu: {
      buildFromTemplate: vi.fn((template) => ({ template })),
      setApplicationMenu: vi.fn(),
    },
    dialog: {
      showMessageBox: vi.fn(),
    },
    shell: {
      openExternal: vi.fn(),
    },
  };
});

describe("Desktop Application Menu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("builds comprehensive menu template with expected top-level menus", () => {
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
    };
    const template = buildAppMenuTemplate(options);
    const labels = template.map((item) => item.label);

    expect(labels).toContain("File");
    expect(labels).toContain("Edit");
    expect(labels).toContain("Agent");
    expect(labels).toContain("View");
    expect(labels).toContain("Window");
    expect(labels).toContain("Help");
  });

  it("dispatches menu:action event via sendMenuAction", () => {
    sendMenuAction(mocks.mockBrowserWindow as unknown as BrowserWindow, "toggle-sidebar");
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith("menu:action", "toggle-sidebar", undefined);
  });

  it("navigates to tab via navigateToTab", () => {
    navigateToTab(mocks.mockBrowserWindow as unknown as BrowserWindow, "settings");
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith("menu:action", "navigate", "settings");
  });

  it("triggers scout action and invokes callback", async () => {
    const onTriggerScout = vi.fn().mockResolvedValue(undefined);
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
      onTriggerScout,
    };

    await triggerScoutAction(options);
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith("menu:action", "trigger-scout", undefined);
    expect(onTriggerScout).toHaveBeenCalled();
  });

  it("toggles pause action and invokes callback with next state", async () => {
    const onTogglePause = vi.fn().mockResolvedValue(undefined);
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
      isPaused: () => false,
      onTogglePause,
    };

    await togglePauseAction(options);
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith("menu:action", "toggle-pause", undefined);
    expect(onTogglePause).toHaveBeenCalledWith(true);
  });

  it("clears incident action and invokes callback", async () => {
    const onClearIncident = vi.fn().mockResolvedValue(undefined);
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
      onClearIncident,
    };

    await clearIncidentAction(options);
    expect(mocks.mockWebContents.send).toHaveBeenCalledWith("menu:action", "clear-incident", undefined);
    expect(onClearIncident).toHaveBeenCalled();
  });

  it("invokes onCheckForUpdates when Check for Updates menu item is clicked", async () => {
    const onCheckForUpdates = vi.fn().mockResolvedValue(true);
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
      onCheckForUpdates,
    };
    const template = buildAppMenuTemplate(options);
    const helpMenu = template.find((m) => m.label === "Help");
    expect(helpMenu).toBeDefined();
    const updateItem = (helpMenu?.submenu as any[])?.find(
      (item) => item.label === "Check for Updates..."
    );
    expect(updateItem).toBeDefined();
    if (updateItem?.click) {
      await updateItem.click();
    }
    expect(onCheckForUpdates).toHaveBeenCalled();
  });

  it("sets up application menu via createAppMenu and setupAppMenu", () => {
    const options = {
      getMainWindow: () => mocks.mockBrowserWindow as unknown as BrowserWindow,
    };
    const menu = createAppMenu(options);
    expect(menu).toBeDefined();
    expect(Menu.buildFromTemplate).toHaveBeenCalled();

    setupAppMenu(options);
    expect(Menu.setApplicationMenu).toHaveBeenCalled();
  });
});
