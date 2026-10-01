import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { VaultView } from "../src/views/VaultView";

describe("VaultView UI", () => {
  const mockCaptureSession = vi.fn();
  const mockCheckSessionHealth = vi.fn();
  const mockGenerateFernetKey = vi.fn();
  const mockSaveSettings = vi.fn();
  const mockGetSettings = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    mockCheckSessionHealth.mockResolvedValue({
      valid: true,
      daysRemaining: 18,
      details: "Active li_at cookie",
    });

    mockCaptureSession.mockResolvedValue({
      success: true,
    });

    mockGenerateFernetKey.mockResolvedValue(
      "kY7x9abc1234567890abcdef1234567890abcdef12="
    );

    mockSaveSettings.mockResolvedValue(true);
    mockGetSettings.mockResolvedValue({
      workerUrl: "https://worker.test",
      apiSecret: "secret",
      encryptionKey: "test-fernet-key-32b=",
    });

    // Attach mock API to window
    window.api = {
      fetchState: vi.fn(),
      executeAction: vi.fn(),
      triggerScout: vi.fn(),
      togglePause: vi.fn(),
      clearIncident: vi.fn(),
      rewriteDraft: vi.fn(),
      saveSession: vi.fn(),
      getSettings: mockGetSettings,
      saveSettings: mockSaveSettings,
      encryptSession: vi.fn(),
      decryptSession: vi.fn(),
      generateFernetKey: mockGenerateFernetKey,
      captureSession: mockCaptureSession,
      checkSessionHealth: mockCheckSessionHealth,
    };
  });

  const renderVault = () => {
    return render(
      <AppProvider>
        <VaultView />
      </AppProvider>
    );
  };

  it("renders Vault header, encryption badge, and status cards", async () => {
    renderVault();

    await waitFor(() => {
      expect(mockCheckSessionHealth).toHaveBeenCalled();
    });

    expect(screen.getByText("LinkedIn Session Vault")).toBeTruthy();
    expect(screen.getByTestId("encryption-badge").textContent).toContain(
      "AES-128-CBC + HMAC-SHA256 Fernet"
    );

    expect(screen.getByText("1-Click Connect LinkedIn")).toBeTruthy();
    expect(screen.getByText("Cookie Health Card")).toBeTruthy();
    expect(screen.getByText("Fernet Encryption Key Card")).toBeTruthy();
    expect(screen.getByText("Cloudflare KV Sync Status")).toBeTruthy();
    expect(screen.getByTestId("kv-payload-status").textContent).toContain(
      "LINKEDIN_SESSION_STATE_ENC in KV"
    );
  });

  it("renders li_at and JSESSIONID cookie status correctly", async () => {
    renderVault();

    await waitFor(() => {
      expect(screen.getByTestId("li-at-status").textContent).toContain(
        "Active (18 days remaining)"
      );
    });

    expect(screen.getByTestId("jsessionid-status").textContent).toContain(
      "Active (CSRF token valid)"
    );
  });

  it("handles Connect LinkedIn button click and renders success banner", async () => {
    renderVault();

    const connectBtn = screen.getByTestId("launch-login-btn");
    expect(connectBtn.textContent).toContain("Launch Secure Login");

    fireEvent.click(connectBtn);

    await waitFor(() => {
      expect(mockCaptureSession).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      const successBanner = screen.getByTestId("capture-success-banner");
      expect(successBanner.textContent).toContain(
        "LinkedIn session captured successfully"
      );
    });
  });

  it("handles Connect LinkedIn button error when window closed before completion", async () => {
    mockCaptureSession.mockResolvedValueOnce({
      success: false,
      error: "Authentication window closed before completion",
    });

    renderVault();

    const connectBtn = screen.getByTestId("launch-login-btn");
    fireEvent.click(connectBtn);

    await waitFor(() => {
      expect(mockCaptureSession).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      const errorBanner = screen.getByTestId("capture-error-banner");
      expect(errorBanner.textContent).toContain(
        "Authentication window closed before completion"
      );
    });
  });

  it("handles Verify Cookie Health button click and updates status", async () => {
    renderVault();

    // Wait for initial mount check to complete
    await waitFor(() => {
      expect(mockCheckSessionHealth).toHaveBeenCalled();
    });

    mockCheckSessionHealth.mockResolvedValueOnce({
      valid: true,
      daysRemaining: 14,
      details: "Active li_at cookie (verified via IPC)",
    });

    const verifyBtn = screen.getByTestId("verify-cookie-health-btn");
    expect(verifyBtn.textContent).toContain("Verify Cookie Health");

    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getByTestId("li-at-status").textContent).toContain(
        "Active (14 days remaining)"
      );
      expect(screen.getByText("Active li_at cookie (verified via IPC)")).toBeTruthy();
    });
  });

  it("handles Generate New Key button click and updates key status", async () => {
    renderVault();

    const generateBtn = screen.getByTestId("generate-key-btn");
    expect(generateBtn.textContent).toContain("Generate New Key");

    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(mockGenerateFernetKey).toHaveBeenCalledTimes(1);
      expect(mockSaveSettings).toHaveBeenCalledWith({
        encryptionKey: "kY7x9abc1234567890abcdef1234567890abcdef12=",
      });
    });

    await waitFor(() => {
      const feedback = screen.getByTestId("key-feedback-msg");
      expect(feedback.textContent).toContain("Generated fresh 32-byte Fernet key");
    });
  });

  it("renders inactive cookie status and un-synced status when session is invalid or missing", async () => {
    mockCheckSessionHealth.mockResolvedValueOnce({
      valid: false,
      daysRemaining: 0,
      details: "No active LinkedIn session found in storage",
    });

    renderVault();

    await waitFor(() => {
      expect(screen.getByTestId("li-at-status").textContent).toContain(
        "No active session"
      );
      expect(screen.getByTestId("jsessionid-status").textContent).toContain(
        "Inactive / Missing"
      );
      expect(screen.getByText("Not Synced")).toBeTruthy();
      expect(screen.getByTestId("kv-payload-status").textContent).toContain(
        "Awaiting session capture"
      );
    });
  });
});
