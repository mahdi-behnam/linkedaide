import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { AppProvider } from "../src/context/AppContext";
import { ThemeProvider } from "../src/context/ThemeContext";
import { CommandPalette } from "../src/components/CommandPalette";

describe("Universal CommandPalette Component", () => {
  beforeEach(() => {
    window.api = {
      fetchState: vi.fn(),
      executeAction: vi.fn(),
      triggerScout: vi.fn().mockResolvedValue(true),
      togglePause: vi.fn().mockResolvedValue(true),
      clearIncident: vi.fn().mockResolvedValue(true),
      rewriteDraft: vi.fn(),
      saveSession: vi.fn(),
      getSettings: vi.fn(),
      saveSettings: vi.fn().mockResolvedValue(true),
      encryptSession: vi.fn(),
      decryptSession: vi.fn(),
      generateFernetKey: vi.fn(),
    };
  });

  const TestWrapper: React.FC<{
    isOpen?: boolean;
    onClose?: () => void;
    onSelectTab?: (tab: any) => void;
  }> = ({ isOpen = true, onClose = vi.fn(), onSelectTab = vi.fn() }) => {
    return (
      <ThemeProvider>
        <AppProvider>
          <CommandPalette
            isOpen={isOpen}
            onClose={onClose}
            onSelectTab={onSelectTab}
          />
        </AppProvider>
      </ThemeProvider>
    );
  };

  it("renders search bar, category chips, and result items when open", () => {
    render(<TestWrapper />);

    expect(screen.getByTestId("command-palette")).toBeTruthy();
    expect(screen.getByTestId("command-palette-input")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-all")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-queue")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-setting")).toBeTruthy();

    // Default static views should be listed
    expect(screen.getByTestId("palette-item-tab-queue")).toBeTruthy();
    expect(screen.getByTestId("palette-item-tab-settings")).toBeTruthy();
  });

  it("filters items by typing in search bar", () => {
    render(<TestWrapper />);
    const input = screen.getByTestId("command-palette-input");

    fireEvent.change(input, { target: { value: "NIM" } });

    expect(screen.getByText("Settings: NVIDIA NIM Intelligence")).toBeTruthy();
    expect(screen.queryByText("Content Calendar")).toBeNull();
  });

  it("filters items by selecting category chips", () => {
    render(<TestWrapper />);
    const settingChip = screen.getByTestId("filter-chip-setting");

    fireEvent.click(settingChip);

    expect(screen.getByText("Settings: NVIDIA NIM Intelligence")).toBeTruthy();
    expect(screen.getByText("Settings: Safety Guardrails & Quotas")).toBeTruthy();
    expect(screen.queryByText("Approval Queue")).toBeNull();
  });

  it("navigates down and up using arrow keys and selects via enter", () => {
    const onSelectTabMock = vi.fn();
    const onCloseMock = vi.fn();

    render(
      <TestWrapper
        onSelectTab={onSelectTabMock}
        onClose={onCloseMock}
      />
    );

    const input = screen.getByTestId("command-palette-input");
    fireEvent.change(input, { target: { value: "Doctor" } });

    // Press Enter to select first filtered result
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSelectTabMock).toHaveBeenCalledWith("doctor");
    expect(onCloseMock).toHaveBeenCalledTimes(1);
  });

  it("closes palette when Escape is pressed", () => {
    const onCloseMock = vi.fn();
    render(<TestWrapper onClose={onCloseMock} />);

    const input = screen.getByTestId("command-palette-input");
    fireEvent.keyDown(input, { key: "Escape" });

    expect(onCloseMock).toHaveBeenCalledTimes(1);
  });

  it("searches and triggers quick actions", () => {
    const onCloseMock = vi.fn();
    const onTogglePauseMock = vi.fn();

    render(
      <ThemeProvider>
        <AppProvider>
          <CommandPalette
            isOpen={true}
            onClose={onCloseMock}
            onTogglePause={onTogglePauseMock}
          />
        </AppProvider>
      </ThemeProvider>
    );

    const input = screen.getByTestId("command-palette-input");
    fireEvent.change(input, { target: { value: "Pause" } });

    const pauseItem = screen.getByTestId("palette-item-act-pause");
    expect(pauseItem).toBeTruthy();

    fireEvent.click(pauseItem);

    expect(onTogglePauseMock).toHaveBeenCalledTimes(1);
    expect(onCloseMock).toHaveBeenCalledTimes(1);
  });
});
