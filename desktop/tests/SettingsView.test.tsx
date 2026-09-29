import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsView } from "../src/views/SettingsView";
import { AppProvider } from "../src/context/AppContext";

describe("SettingsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    window.api = {
      fetchState: vi.fn().mockResolvedValue({
        pending_actions: [],
        daily_counters: {
          date: "2026-09-29",
          comments_executed: 0,
          posts_executed: 0,
          suggestions_sent: 0,
        },
        history: [],
        incident: null,
        paused: false,
      }),
      executeAction: vi.fn().mockResolvedValue({ success: true }),
      triggerScout: vi.fn().mockResolvedValue(true),
      togglePause: vi.fn().mockResolvedValue(true),
      clearIncident: vi.fn().mockResolvedValue(true),
      rewriteDraft: vi.fn().mockResolvedValue("Rewritten draft text"),
      saveSession: vi.fn().mockResolvedValue(true),
      getSettings: vi.fn().mockResolvedValue({
        workerUrl: "https://relay.custom.workers.dev",
        apiSecret: "secret-token-123",
        encryptionKey: "test-fernet-key-32bytes-base64-padding==",
        autoRefreshInterval: 300,
        executionMode: "cloud",
        headless: true,
        minimizeToTray: true,
        notificationsEnabled: true,
        maxCommentsPerDay: 20,
        maxPostsPerDay: 5,
        maxSuggestionsPerRun: 12,
        actionTtlHours: 48,
      }),
      saveSettings: vi.fn().mockResolvedValue(true),
      encryptSession: vi.fn().mockResolvedValue("encrypted"),
      decryptSession: vi.fn().mockResolvedValue("decrypted"),
      generateFernetKey: vi.fn().mockResolvedValue("generated-fernet-key=="),
    };
  });

  const renderWithContext = () => {
    return render(
      <AppProvider>
        <SettingsView />
      </AppProvider>
    );
  };

  it("renders settings header and sections", async () => {
    renderWithContext();
    expect(screen.getByText("Agent Configuration & Settings")).toBeTruthy();
    expect(screen.getByText("Execution Architecture Mode")).toBeTruthy();
    expect(screen.getByText("Cloudflare Worker Edge Relay")).toBeTruthy();
    expect(
      screen.getByText("Session Vault Encryption (Fernet AES-128-CBC)")
    ).toBeTruthy();
  });

  it("loads existing settings on mount", async () => {
    renderWithContext();
    await waitFor(() => {
      const urlInput = screen.getByPlaceholderText(
        "https://relay.your-subdomain.workers.dev"
      ) as HTMLInputElement;
      expect(urlInput.value).toBe("https://relay.custom.workers.dev");
    });
  });

  it("toggles execution mode between cloud and local", async () => {
    renderWithContext();
    const localRadio = screen.getByLabelText(
      /Local Playwright Runner/i
    ) as HTMLInputElement;
    fireEvent.click(localRadio);
    expect(localRadio.checked).toBe(true);
  });

  it("generates a new Fernet key when button is clicked", async () => {
    renderWithContext();
    const generateBtn = screen.getByRole("button", { name: /Generate Key/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(window.api.generateFernetKey).toHaveBeenCalled();
    });
  });

  it("tests connection and displays latency", async () => {
    renderWithContext();
    const testBtn = screen.getByRole("button", { name: /Test Connection/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(window.api.fetchState).toHaveBeenCalled();
      expect(
        screen.getByText(/Connected successfully to Cloudflare Worker API/i)
      ).toBeTruthy();
    });
  });

  it("saves updated settings when form is submitted", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const saveBtn = screen.getByRole("button", {
      name: /Save & Apply Settings/i,
    });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          workerUrl: "https://relay.custom.workers.dev",
          executionMode: "cloud",
        })
      );
      expect(screen.getByText("Settings Saved & Applied")).toBeTruthy();
    });
  });
});
