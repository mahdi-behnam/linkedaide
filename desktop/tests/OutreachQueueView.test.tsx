import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import {
  OutreachQueueView,
} from "../src/views/OutreachQueueView";
import { ConnectionRequestAction } from "../src/types";

describe("OutreachQueueView", () => {
  const mockCandidates: ConnectionRequestAction[] = [
    {
      id: "conn-test-1",
      profile_url: "https://linkedin.com/in/alice-vance-dist",
      target_name: "Alice Vance",
      target_headline: "Staff Distributed Systems Engineer at Cloudflare",
      mutual_context: "Commented on Alice's post regarding distributed cache invalidation",
      note_text: "Hi Alice, really enjoyed your breakdown on edge cache invalidation tradeoffs.",
      status: "pending",
      created_at: "2026-09-30T08:15:00Z",
    },
    {
      id: "conn-test-2",
      profile_url: "https://linkedin.com/in/marcus-chen-ai",
      target_name: "Marcus Chen",
      target_headline: "Principal Research Scientist at NVIDIA NIM Team",
      mutual_context: "Participated in thread discussing speculative decoding speedups",
      note_text: "Hey Marcus, your insights on speculative decoding latency boundaries were spot on.",
      status: "pending",
      created_at: "2026-09-30T07:45:00Z",
    },
    {
      id: "conn-test-3",
      profile_url: "https://linkedin.com/in/sarah-jenkins-dev",
      target_name: "Sarah Jenkins",
      target_headline: "Head of AI Infrastructure at LangChain",
      mutual_context: "Engaged on discussion about persistent state checkpoints",
      note_text: "Hi Sarah, loved your analysis on checkpoint durability across multi-agent pipelines.",
      status: "pending",
      created_at: "2026-09-29T22:10:00Z",
    },
  ];

  beforeEach(() => {
    window.api = {
      fetchState: vi.fn(),
      executeAction: vi.fn().mockResolvedValue({ success: true, message: "Action processed" }),
      executeConnectionAction: vi.fn().mockResolvedValue({ success: true, message: "Invitation sent" }),
      triggerScout: vi.fn().mockResolvedValue(true),
      togglePause: vi.fn().mockResolvedValue(true),
      clearIncident: vi.fn().mockResolvedValue(true),
      rewriteDraft: vi.fn().mockImplementation(async (text: string, tone: string) => {
        return `${text} [rewritten with ${tone} tone]`;
      }),
      saveSession: vi.fn().mockResolvedValue(true),
      getSettings: vi.fn(),
      saveSettings: vi.fn().mockResolvedValue(true),
      encryptSession: vi.fn(),
      decryptSession: vi.fn(),
      generateFernetKey: vi.fn(),
    };
  });

  const renderOutreachQueue = (initialItems?: ConnectionRequestAction[]) => {
    return render(
      <AppProvider>
        <OutreachQueueView initialItems={initialItems ?? mockCandidates} />
      </AppProvider>
    );
  };

  it("renders candidate queue header, count pill, and daily cap quota badge", () => {
    renderOutreachQueue();

    expect(screen.getByText("Outreach Queue")).toBeTruthy();
    expect(screen.getByTestId("pending-count-pill").textContent).toContain("3 Pending");
    expect(screen.getByTestId("connection-quota-badge")).toBeTruthy();
    expect(screen.getAllByText("Alice Vance").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Marcus Chen").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Sarah Jenkins").length).toBeGreaterThanOrEqual(1);
  });

  it("selecting candidate card shows details, profile link, and mutual context citation", () => {
    renderOutreachQueue();

    // Default first candidate Alice Vance is selected
    expect(screen.getByTestId("mutual-context-quote").textContent).toContain(
      "Commented on Alice's post regarding distributed cache invalidation"
    );
    const profileLink = screen.getByTestId("profile-link") as HTMLAnchorElement;
    expect(profileLink.href).toBe("https://linkedin.com/in/alice-vance-dist");

    // Click on Marcus Chen card
    const marcusCard = screen.getByTestId("candidate-card-conn-test-2");
    fireEvent.click(marcusCard);

    expect(screen.getByTestId("mutual-context-quote").textContent).toContain(
      "Participated in thread discussing speculative decoding speedups"
    );
  });

  it("editing note updates character countdown progress and enforces 300 char limit warning", () => {
    renderOutreachQueue();

    const textarea = screen.getByTestId("note-editor-textarea") as HTMLTextAreaElement;
    const charPill = screen.getByTestId("char-count-pill");

    // Short note
    const shortText = "Testing customized note message for connection.";
    fireEvent.change(textarea, { target: { value: shortText } });

    expect(textarea.value).toBe(shortText);
    expect(charPill.textContent).toContain(`${shortText.length} / 300 chars`);
    expect(screen.queryByTestId("limit-warning-text")).toBeNull();
    expect(screen.queryByTestId("approaching-warning-text")).toBeNull();

    // Approaching limit (> 280 chars)
    const warningText = "A".repeat(285);
    fireEvent.change(textarea, { target: { value: warningText } });
    expect(charPill.textContent).toContain("285 / 300 chars");
    expect(screen.getByTestId("approaching-warning-text")).toBeTruthy();
    expect(screen.queryByTestId("limit-warning-text")).toBeNull();

    // Over limit (> 300 chars)
    const overLimitText = "B".repeat(305);
    fireEvent.change(textarea, { target: { value: overLimitText } });
    expect(charPill.textContent).toContain("305 / 300 chars");
    expect(screen.getByTestId("limit-warning-text")).toBeTruthy();

    // Approve button should be disabled when over limit
    const approveBtn = screen.getByTestId("approve-button") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(true);
  });

  it("tone quick-pills apply tone rewrites to note editor", async () => {
    renderOutreachQueue();

    const textarea = screen.getByTestId("note-editor-textarea") as HTMLTextAreaElement;

    // Click Casual tone
    const casualBtn = screen.getByTestId("tone-pill-casual");
    fireEvent.click(casualBtn);

    expect(textarea.value.length).toBeGreaterThan(0);

    // Click Technical tone
    const technicalBtn = screen.getByTestId("tone-pill-technical");
    fireEvent.click(technicalBtn);

    expect(textarea.value.length).toBeGreaterThan(0);

    // Click Concise tone
    const conciseBtn = screen.getByTestId("tone-pill-concise");
    fireEvent.click(conciseBtn);

    expect(textarea.value.length).toBeGreaterThan(0);
  });

  it("approves connection request and marks candidate approved", async () => {
    renderOutreachQueue();

    const approveBtn = screen.getByTestId("approve-button");
    expect(approveBtn).toBeTruthy();

    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(approveBtn.textContent).toContain("Approved");
      expect(screen.getByTestId("pending-count-pill").textContent).toContain("2 Pending");
    });
  });

  it("rejects connection request and marks candidate rejected", async () => {
    renderOutreachQueue();

    const rejectBtn = screen.getByTestId("reject-button") as HTMLButtonElement;
    expect(rejectBtn).toBeTruthy();

    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(rejectBtn.disabled).toBe(true);
      expect(screen.getByTestId("pending-count-pill").textContent).toContain("2 Pending");
    });
  });

  it("renders empty state cleanly when queue has no candidates", () => {
    renderOutreachQueue([]);

    expect(screen.getByTestId("pending-count-pill").textContent).toContain("0 Pending");
    expect(screen.getByText("No connection candidates queued")).toBeTruthy();
    expect(screen.getByText("Select a candidate on the left to inspect details")).toBeTruthy();
    expect(screen.getByTestId("connection-quota-badge").textContent).toContain("0 / 10");
  });

  it("renders standard empty state when rendered without initialItems", () => {
    render(
      <AppProvider>
        <OutreachQueueView />
      </AppProvider>
    );

    expect(screen.getByTestId("pending-count-pill").textContent).toContain("0 Pending");
    expect(screen.getByText("No connection candidates queued")).toBeTruthy();
    expect(screen.getByText("Select a candidate on the left to inspect details")).toBeTruthy();
  });

  it("synchronizes candidates when initialItems updates dynamically", () => {
    const { rerender } = renderOutreachQueue([mockCandidates[0]]);
    expect(screen.getByTestId("pending-count-pill").textContent).toContain("1 Pending");

    rerender(
      <AppProvider>
        <OutreachQueueView initialItems={mockCandidates} />
      </AppProvider>
    );

    expect(screen.getByTestId("pending-count-pill").textContent).toContain("3 Pending");
  });

  it("triggers refresh when clicking Refresh button in header", async () => {
    renderOutreachQueue();
    const refreshBtn = screen.getByLabelText("Refresh outreach queue");
    expect(refreshBtn).toBeTruthy();

    fireEvent.click(refreshBtn);
    await waitFor(() => {
      expect(window.api.fetchState).toHaveBeenCalled();
    });
  });
});

