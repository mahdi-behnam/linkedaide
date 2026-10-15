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
      fetchNimModels: vi.fn().mockResolvedValue({
        success: true,
        models: [
          "meta/llama-3.1-70b-instruct",
          "meta/llama-3.3-70b-instruct",
          "mistralai/mistral-large-2-instruct",
          "deepseek-ai/deepseek-r1",
        ],
      }),
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

  it("invokes window.api.testConnection with user inputs when available", async () => {
    window.api.testConnection = vi.fn().mockResolvedValue({
      success: true,
      latencyMs: 42,
    });

    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const urlInput = screen.getByPlaceholderText(
      "https://relay.your-subdomain.workers.dev"
    ) as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "https://new-worker.workers.dev" } });

    const secretInput = screen.getByPlaceholderText(
      "Enter DESKTOP_API_SECRET"
    ) as HTMLInputElement;
    fireEvent.change(secretInput, { target: { value: "new-secret-123" } });

    const testBtn = screen.getByRole("button", { name: /Test Connection/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(window.api.testConnection).toHaveBeenCalledWith({
        workerUrl: "https://new-worker.workers.dev",
        apiSecret: "new-secret-123",
      });
      expect(
        screen.getByText(/Connected successfully to Cloudflare Worker API/i)
      ).toBeTruthy();
      expect(screen.getByText("42 ms")).toBeTruthy();
    });
  });

  it("displays connection error when testConnection fails", async () => {
    window.api.testConnection = vi.fn().mockRejectedValue(
      new Error("Authentication failed (401 Unauthorized): Invalid Desktop API Secret.")
    );

    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const testBtn = screen.getByRole("button", { name: /Test Connection/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(
        screen.getByText(
          /Connection error: Authentication failed \(401 Unauthorized\)/i
        )
      ).toBeTruthy();
    });
  });

  it("saves updated settings when form is modified and saved", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    // Unsaved changes bar should not be present initially
    expect(screen.queryByTestId("unsaved-changes-bar")).toBeNull();

    // Modify a setting
    const urlInput = screen.getByPlaceholderText(
      "https://relay.your-subdomain.workers.dev"
    ) as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "https://relay.modified.workers.dev" } });

    // Floating save and discard buttons appear
    const saveBtn = screen.getByTestId("save-settings-btn");
    expect(saveBtn).toBeTruthy();
    expect(screen.getByTestId("discard-settings-btn")).toBeTruthy();

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          workerUrl: "https://relay.modified.workers.dev",
          executionMode: "cloud",
        })
      );
      expect(screen.getByText("Settings Saved & Applied")).toBeTruthy();
    });
  });

  it("shows unsaved changes bar when edited and hides on discard", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    expect(screen.queryByTestId("unsaved-changes-bar")).toBeNull();

    const urlInput = screen.getByPlaceholderText(
      "https://relay.your-subdomain.workers.dev"
    ) as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "https://relay.temporary.workers.dev" } });

    expect(screen.getByTestId("unsaved-changes-bar")).toBeTruthy();

    const discardBtn = screen.getByTestId("discard-settings-btn");
    fireEvent.click(discardBtn);

    expect(urlInput.value).toBe("https://relay.custom.workers.dev");
    expect(screen.queryByTestId("unsaved-changes-bar")).toBeNull();
  });

  it("allows selecting an NVIDIA NIM model from dropdown and saving", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const modelSelect = screen.getByLabelText("Primary NIM Model") as HTMLSelectElement;
    fireEvent.change(modelSelect, { target: { value: "meta/llama-3.3-70b-instruct" } });

    const keyInput = screen.getByPlaceholderText(
      "Enter NVIDIA_NIM_API_KEY (nvapi-...)"
    ) as HTMLInputElement;
    fireEvent.change(keyInput, { target: { value: "nvapi-test-token" } });

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          nimModel: "meta/llama-3.3-70b-instruct",
          nimApiKey: "nvapi-test-token",
        })
      );
    });
  });

  it("fetches available models from NVIDIA and populates the selector", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const fetchBtn = screen.getByRole("button", {
      name: /Fetch Models from NVIDIA/i,
    });
    fireEvent.click(fetchBtn);

    await waitFor(() => {
      expect(window.api.fetchNimModels).toHaveBeenCalled();
      expect(screen.getByText(/Loaded 4 models from NVIDIA/i)).toBeTruthy();
      expect(screen.getByText("deepseek-ai/deepseek-r1")).toBeTruthy();
    });
  });

  it("allows selecting custom model and typing manual identifier", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const modelSelect = screen.getByLabelText("Primary NIM Model") as HTMLSelectElement;
    fireEvent.change(modelSelect, { target: { value: "__custom__" } });

    const customInput = screen.getByLabelText("Custom NIM Model Identifier") as HTMLInputElement;
    fireEvent.change(customInput, { target: { value: "custom-org/special-model-v1" } });

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          nimModel: "custom-org/special-model-v1",
        })
      );
    });
  });

  it("displays error banner when fetching models fails", async () => {
    window.api.fetchNimModels = vi.fn().mockResolvedValue({
      success: false,
      models: [],
      error: "NVIDIA API rate limit exceeded",
    });

    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const fetchBtn = screen.getByRole("button", {
      name: /Fetch Models from NVIDIA/i,
    });
    fireEvent.click(fetchBtn);

    await waitFor(() => {
      expect(screen.getByText(/NVIDIA API rate limit exceeded/i)).toBeTruthy();
    });
  });

  it("allows configuring and saving GitHub Actions cloud runner dispatch settings", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    expect(screen.getByText("GitHub Actions Cloud Runner Dispatch")).toBeTruthy();

    const ownerInput = screen.getByPlaceholderText("e.g. mahdi-behnam") as HTMLInputElement;
    fireEvent.change(ownerInput, { target: { value: "my-github-user" } });

    const repoInput = screen.getByPlaceholderText("e.g. linkedin-hitl-agent") as HTMLInputElement;
    fireEvent.change(repoInput, { target: { value: "my-linkedin-repo" } });

    const patInput = screen.getByPlaceholderText(
      "Enter GITHUB_DISPATCH_PAT (ghp_... or github_pat_...)"
    ) as HTMLInputElement;
    expect(patInput.type).toBe("password");
    fireEvent.change(patInput, { target: { value: "ghp_securetoken9876543210" } });

    // Toggle show/hide
    const patToggle = screen.getByRole("button", { name: /Toggle GitHub PAT visibility/i });
    fireEvent.click(patToggle);
    expect(patInput.type).toBe("text");

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          githubRepoOwner: "my-github-user",
          githubRepoName: "my-linkedin-repo",
          githubDispatchPat: "ghp_securetoken9876543210",
        })
      );
    });
  });

  it("allows configuring and saving maxConnectionsPerDay", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const connInput = screen.getByLabelText("Max Connections / Day") as HTMLInputElement;
    fireEvent.change(connInput, { target: { value: "18" } });

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          maxConnectionsPerDay: 18,
        })
      );
    });
  });

  it("allows selecting, filtering, and saving timezone preference", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    expect(screen.getByText("Regional & Timezone Settings")).toBeTruthy();
    const tzSelect = screen.getByTestId("timezone-select") as HTMLSelectElement;
    expect(tzSelect).toBeTruthy();

    // Change timezone to America/New_York
    fireEvent.change(tzSelect, { target: { value: "America/New_York" } });
    expect(tzSelect.value).toBe("America/New_York");

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          timezone: "America/New_York",
        })
      );
    });
  });

  it("renders ScoutTargetingCard and allows adding/removing focus areas and normalized hashtags", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    expect(screen.getByText("Scout Targets & Focus Topics")).toBeTruthy();

    // Add focus area
    const focusInput = screen.getByPlaceholderText(/Add focus topic/i) as HTMLInputElement;
    fireEvent.change(focusInput, { target: { value: "Distributed AI" } });
    fireEvent.keyDown(focusInput, { key: "Enter", code: "Enter" });

    expect(screen.getByText("Distributed AI")).toBeTruthy();

    // Add hashtag without leading # (should auto-normalize)
    const hashtagInput = screen.getByPlaceholderText(/Add hashtag/i) as HTMLInputElement;
    fireEvent.change(hashtagInput, { target: { value: "agentic" } });
    fireEvent.keyDown(hashtagInput, { key: "Enter", code: "Enter" });

    // Should display normalized without leading hash in pill text
    expect(screen.getByText("agentic")).toBeTruthy();

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          userFocusAreas: ["Distributed AI"],
          targetHashtags: ["#agentic"],
        })
      );
    });

    // Remove the focus area
    const removeFocusBtn = screen.getByLabelText("Remove focus area Distributed AI");
    fireEvent.click(removeFocusBtn);
    expect(screen.queryByText("Distributed AI")).toBeNull();
  });

  it("allows adding and removing direct scout target URLs", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    const urlInput = screen.getByPlaceholderText(/linkedin.com\/company/i) as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "https://www.linkedin.com/company/anthropic/posts/" } });

    const addBtn = screen.getByRole("button", { name: "Add target URL" });
    fireEvent.click(addBtn);

    expect(screen.getByText("https://www.linkedin.com/company/anthropic/posts/")).toBeTruthy();

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          scoutTargetUrls: ["https://www.linkedin.com/company/anthropic/posts/"],
        })
      );
    });

    // Remove URL
    const removeUrlBtn = screen.getByLabelText("Remove URL https://www.linkedin.com/company/anthropic/posts/");
    fireEvent.click(removeUrlBtn);
    expect(screen.queryByText("https://www.linkedin.com/company/anthropic/posts/")).toBeNull();
  });

  it("renders ScoutEngineCard and allows configuring scroll depth, multiplier, confidence, and pre-reactions", async () => {
    renderWithContext();
    await waitFor(() => {
      expect(window.api.getSettings).toHaveBeenCalled();
    });

    expect(screen.getByText("Scout Engine & Scraping Parameters")).toBeTruthy();

    // Change scroll depth to 3 screens
    const scrollSelect = screen.getByLabelText("Feed Scroll Depth") as HTMLSelectElement;
    fireEvent.change(scrollSelect, { target: { value: "3" } });
    expect(scrollSelect.value).toBe("3");

    // Change candidate multiplier to 4x
    const multiplierSelect = screen.getByLabelText("Candidate Pool Multiplier") as HTMLSelectElement;
    fireEvent.change(multiplierSelect, { target: { value: "4" } });
    expect(multiplierSelect.value).toBe("4");

    // Change min triage confidence
    const confidenceSlider = screen.getByLabelText("Min Triage Confidence") as HTMLInputElement;
    fireEvent.change(confidenceSlider, { target: { value: "0.85" } });
    expect(screen.getByText("85%")).toBeTruthy();

    // Change max comment words
    const maxWordsInput = screen.getByLabelText("Max Comment Words") as HTMLInputElement;
    fireEvent.change(maxWordsInput, { target: { value: "60" } });
    expect(maxWordsInput.value).toBe("60");

    // Enable pre-comment reaction
    const preReactionCheckbox = screen.getByRole("checkbox", { name: /Organic Pre-Comment Reaction/i }) as HTMLInputElement;
    fireEvent.click(preReactionCheckbox);
    expect(preReactionCheckbox.checked).toBe(true);

    // Select reaction type
    const reactionSelect = screen.getByLabelText("Type:") as HTMLSelectElement;
    fireEvent.change(reactionSelect, { target: { value: "insightful" } });
    expect(reactionSelect.value).toBe("insightful");

    const saveBtn = screen.getByTestId("save-settings-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(window.api.saveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          feedScrollScreens: 3,
          candidatePoolMultiplier: 4,
          minTriageConfidence: 0.85,
          maxCommentWords: 60,
          enablePreCommentReaction: true,
          defaultReactionType: "insightful",
        })
      );
    });
  });
});
