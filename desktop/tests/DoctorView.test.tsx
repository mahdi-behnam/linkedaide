import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { DoctorView } from "../src/views/DoctorView";

describe("DoctorView", () => {
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
          connections_sent: 0,
        },
        history: [],
        incident: null,
        paused: false,
      }),
      executeAction: vi.fn(),
      triggerScout: vi.fn(),
      togglePause: vi.fn(),
      clearIncident: vi.fn(),
      rewriteDraft: vi.fn(),
      saveSession: vi.fn(),
      getSettings: vi.fn().mockResolvedValue({
        workerUrl: "https://relay.test.workers.dev",
        apiSecret: "secret-key",
        encryptionKey: "test-fernet-key-32b=",
        cloudflareAccountId: "acc-123",
        cloudflareKvNamespaceId: "kv-456",
        nimApiKey: "nvapi-test",
        notificationsEnabled: true,
        maxCommentsPerDay: 15,
      }),
      saveSettings: vi.fn(),
      encryptSession: vi.fn(),
      decryptSession: vi.fn(),
      generateFernetKey: vi.fn(),
      checkSessionHealth: vi.fn().mockResolvedValue({
        valid: true,
        daysRemaining: 18,
        details: "Active li_at cookie",
      }),
    };
  });

  const renderDoctor = () => {
    return render(
      <AppProvider>
        <DoctorView />
      </AppProvider>
    );
  };

  it("renders standard empty state before doctor checks are executed", async () => {
    renderDoctor();

    await waitFor(() => {
      expect(screen.getByText("System Diagnostics")).toBeTruthy();
      expect(screen.getByText("Awaiting Execution")).toBeTruthy();
      expect(
        screen.getByText("No diagnostic checks performed yet")
      ).toBeTruthy();
      expect(
        screen.getByText(/Click 'Run Doctor Checks' above to verify runtime dependencies/i)
      ).toBeTruthy();
    });
  });

  it("runs doctor checks upon clicking Run Doctor Checks and displays results", async () => {
    renderDoctor();

    const runBtn = screen.getByTestId("run-doctor-btn");
    expect(runBtn).toBeTruthy();

    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText("Cloudflare KV State Store")).toBeTruthy();
      expect(screen.getByText("Telegram Relay Worker")).toBeTruthy();
      expect(screen.getByText("LinkedIn Playwright Session")).toBeTruthy();
      expect(screen.getByText("NVIDIA NIM Connectivity")).toBeTruthy();
      expect(screen.getByText("Safety & Circuit Breaker")).toBeTruthy();
      expect(screen.getByText("Environment Configuration")).toBeTruthy();
    });

    expect(screen.queryByText("No diagnostic checks performed yet")).toBeNull();
  });

  it("audits configured environment variables from settings and telemetry", async () => {
    renderDoctor();

    await waitFor(() => {
      expect(screen.getByText(/Variables Configured/i)).toBeTruthy();
      expect(screen.getByText("NVIDIA_NIM_API_KEY")).toBeTruthy();
      expect(screen.getByText("SESSION_ENCRYPTION_KEY")).toBeTruthy();
      expect(screen.getByText("CF_KV_NAMESPACE_ID")).toBeTruthy();
    });
  });
});
