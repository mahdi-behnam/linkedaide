import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import {
  ApprovalQueueView,
  PendingItem,
} from "../src/views/ApprovalQueueView";

describe("ApprovalQueueView", () => {
  beforeEach(() => {
    window.api = {
      fetchState: vi.fn(),
      executeAction: vi
        .fn()
        .mockResolvedValue({ success: true, message: "Action processed" }),
      triggerScout: vi.fn().mockResolvedValue(true),
      togglePause: vi.fn().mockResolvedValue(true),
      clearIncident: vi.fn().mockResolvedValue(true),
      rewriteDraft: vi
        .fn()
        .mockImplementation(async (text: string, tone: string) => {
          return `${text} [rewritten with ${tone}]`;
        }),
      saveSession: vi.fn().mockResolvedValue(true),
      getSettings: vi.fn(),
      saveSettings: vi.fn().mockResolvedValue(true),
      encryptSession: vi.fn(),
      decryptSession: vi.fn(),
      generateFernetKey: vi.fn(),
    };
  });

  const renderApprovalQueue = (props?: { initialItems?: PendingItem[] }) => {
    return render(
      <AppProvider>
        <ApprovalQueueView {...props} />
      </AppProvider>
    );
  };

  it("renders pending items list", () => {
    renderApprovalQueue();

    // Check header and pending count pill
    expect(screen.getByText("Approval Queue")).toBeTruthy();
    expect(screen.getByTestId("pending-count-pill").textContent).toContain("3 Pending");

    // Check authors in pending cards
    expect(screen.getByText("Satya Nadella")).toBeTruthy();
    expect(screen.getByText("Harrison Chase")).toBeTruthy();
    expect(screen.getByText("Operator (Self)")).toBeTruthy();

    // Check match percentages and topic badges
    expect(screen.getByText("94% Match")).toBeTruthy();
    expect(screen.getAllByText("Enterprise AI").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Agent Orchestration")).toBeTruthy();
  });

  it("selecting item shows details in inspector", () => {
    renderApprovalQueue();

    // Initially, Satya Nadella is selected
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );

    // Click on Harrison Chase's card
    const harrisonCard = screen.getByTestId("pending-card-act-4c9a2d");
    fireEvent.click(harrisonCard);

    // Inspector should now display Harrison Chase's target excerpt and details
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );
    expect(
      screen.getByText(/Harrison Chase, Co-Founder and CEO at LangChain/)
    ).toBeTruthy();
    expect(screen.getByText("supportive synthesis")).toBeTruthy();
  });

  it("editing draft text updates character count", () => {
    renderApprovalQueue();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;

    // Type a short text
    const shortText = "Testing draft character counter updates.";
    fireEvent.change(textarea, { target: { value: shortText } });

    expect(textarea.value).toBe(shortText);
    const counter = screen.getByTestId("char-word-counter");
    expect(counter.textContent).toContain(`${shortText.length} chars`);
    expect(counter.textContent).toContain("5 words");

    // Verify length indicator indicates target range when under 150 chars
    expect(screen.getByTestId("length-indicator").textContent).toContain(
      "Target: 150-350 chars"
    );

    // Now type a sweet-spot text (between 150 and 350 chars, 25 to 60 words)
    const sweetSpotText =
      "Reliable verification pipelines are essential for production agent systems. Combining persistent KV edge storage with deterministic graph workflows eliminates transient checkpoint failures and ensures reproducible enterprise operations across scale.";
    fireEvent.change(textarea, { target: { value: sweetSpotText } });

    expect(screen.getByTestId("sweet-spot-badge")).toBeTruthy();
    expect(screen.getByTestId("sweet-spot-badge").textContent).toContain("Sweet Spot");
  });

  it("clicking tone pill calls rewriteDraft", async () => {
    renderApprovalQueue();

    const technicalPill = screen.getByTestId("tone-pill-technical");
    expect(technicalPill).toBeTruthy();

    fireEvent.click(technicalPill);

    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.stringContaining("autonomous verification pipelines"),
        "technical"
      );
    });

    // Check that draft textarea is updated in place
    await waitFor(() => {
      const textarea = screen.getByTestId(
        "draft-editor-textarea"
      ) as HTMLTextAreaElement;
      expect(textarea.value).toContain("[rewritten with technical]");
    });
  });

  it("clicking Approve calls executeAction('approve', ...) and removes item", async () => {
    renderApprovalQueue();

    expect(screen.getByTestId("pending-card-act-8f4b1e")).toBeTruthy();
    const approveBtn = screen.getByTestId("approve-action-btn");

    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "approve",
        "act-8f4b1e"
      );
    });

    // Item should be removed from the queue
    await waitFor(() => {
      expect(screen.queryByTestId("pending-card-act-8f4b1e")).toBeNull();
    });

    // Next item (Harrison Chase) should now be selected
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );
    expect(screen.getByTestId("pending-count-pill").textContent).toContain("2 Pending");
  });

  it("clicking Reject calls executeAction('reject', ...) and removes item", async () => {
    renderApprovalQueue();

    expect(screen.getByTestId("pending-card-act-8f4b1e")).toBeTruthy();
    const rejectBtn = screen.getByTestId("reject-action-btn");

    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "reject",
        "act-8f4b1e"
      );
    });

    // Item should be removed from the queue
    await waitFor(() => {
      expect(screen.queryByTestId("pending-card-act-8f4b1e")).toBeNull();
    });

    expect(screen.getByTestId("pending-count-pill").textContent).toContain("2 Pending");
  });

  it("renders empty state when no items remain", () => {
    renderApprovalQueue({ initialItems: [] });

    expect(screen.getByTestId("empty-queue-state")).toBeTruthy();
    expect(
      screen.getByText("All caught up. Zero pending approvals.")
    ).toBeTruthy();
  });

  it("filters items using search input", () => {
    renderApprovalQueue();

    const searchInput = screen.getByTestId(
      "queue-search-input"
    ) as HTMLInputElement;

    fireEvent.change(searchInput, { target: { value: "Harrison" } });

    expect(screen.getByTestId("pending-card-act-4c9a2d")).toBeTruthy();
    expect(screen.queryByTestId("pending-card-act-8f4b1e")).toBeNull();
    expect(screen.queryByTestId("pending-card-act-2e5f8b")).toBeNull();
  });

  it("clicking Regenerate calls rewriteDraft with regenerate tone", async () => {
    renderApprovalQueue();

    const regenerateBtn = screen.getByTestId("regenerate-action-btn");
    fireEvent.click(regenerateBtn);

    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "regenerate"
      );
    });

    await waitFor(() => {
      const textarea = screen.getByTestId(
        "draft-editor-textarea"
      ) as HTMLTextAreaElement;
      expect(textarea.value).toContain("[rewritten with regenerate]");
    });
  });
});
