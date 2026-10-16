import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { ApprovalQueueView } from "../src/views/ApprovalQueueView";
import { KeyboardShortcutsModal } from "../src/components/KeyboardShortcutsModal";

describe("ApprovalQueue Keyboard Shortcuts and HUD Cheat Sheet", () => {
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

const fixturePendingItems = [
  {
    id: "act-8f4b1e",
    actionType: "comment" as const,
    author: "Satya Nadella",
    headline: "Chairman and CEO at Microsoft",
    postUrl: "https://linkedin.com/feed/update/urn:li:activity:7245890012",
    postExcerpt:
      "Autonomous AI systems in the enterprise require reliable verification architectures before scaling critical decision workflows.",
    draftText:
      "The compounding returns on autonomous verification pipelines highlight why deterministic guardrails matter more than raw model scale.",
    confidence: 0.94,
    reasoning: "High signal post.",
    engagementStyle: "technical_deep_dive",
    createdAt: "15m ago",
    topic: "Enterprise AI",
  },
  {
    id: "act-4c9a2d",
    actionType: "comment" as const,
    author: "Harrison Chase",
    headline: "Co-Founder and CEO at LangChain",
    postUrl: "https://linkedin.com/feed/update/urn:li:activity:7245834921",
    postExcerpt:
      "Stateful agent workflows in production: why checkpoint persistence and deterministic graph transitions prevent cascading failure loops.",
    draftText:
      "Separating workflow orchestration state from transient LLM checkpoints is the key architectural leap.",
    confidence: 0.91,
    reasoning: "LangGraph orchestration.",
    engagementStyle: "supportive_synthesis",
    createdAt: "35m ago",
    topic: "Agent Orchestration",
  },
  {
    id: "act-2e5f8b",
    actionType: "post" as const,
    author: "Operator (Self)",
    headline: "Original LinkedAide Post",
    postUrl: "",
    postExcerpt:
      "Original thought leadership draft analyzing human-in-the-loop safety boundaries and session isolation.",
    draftText:
      "Why human-in-the-loop is the prerequisite for enterprise agent deployment.",
    confidence: 0.88,
    reasoning: "Feed trends.",
    engagementStyle: "technical_deep_dive",
    createdAt: "1h ago",
    topic: "Thought Leadership",
  },
];

  const renderView = () => {
    return render(
      <AppProvider>
        <ApprovalQueueView initialItems={fixturePendingItems} />
      </AppProvider>
    );
  };

  it("j and k change selected item index", () => {
    renderView();

    // Initially, Satya Nadella (item 0) is selected
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );

    // Press 'j' -> moves to Harrison Chase (item 1)
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );

    // Press 'j' again -> moves to Operator (item 2)
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Original thought leadership draft"
    );

    // Press 'j' at bottom -> stays on item 2
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Original thought leadership draft"
    );

    // Press 'k' -> moves back up to Harrison Chase (item 1)
    fireEvent.keyDown(window, { key: "k" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );

    // Press 'k' again -> moves back up to Satya Nadella (item 0)
    fireEvent.keyDown(window, { key: "k" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );

    // Press 'k' at top -> stays on item 0
    fireEvent.keyDown(window, { key: "k" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );
  });

  it("ArrowDown and ArrowUp change selected item index", () => {
    renderView();

    // Initial state: Satya
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );

    // ArrowDown -> Harrison
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );

    // ArrowUp -> Satya
    fireEvent.keyDown(window, { key: "ArrowUp" });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );
  });

  it("a triggers approve action on currently selected item", async () => {
    renderView();

    expect(screen.getByTestId("pending-card-act-8f4b1e")).toBeTruthy();

    // Press 'a' to approve Satya's item
    fireEvent.keyDown(window, { key: "a" });

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "approve",
        "act-8f4b1e",
        expect.any(String)
      );
    });

    // Item is removed and next item (Harrison) is selected
    await waitFor(() => {
      expect(screen.queryByTestId("pending-card-act-8f4b1e")).toBeNull();
    });
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Stateful agent workflows in production"
    );
  });

  it("r triggers reject action on currently selected item", async () => {
    renderView();

    expect(screen.getByTestId("pending-card-act-8f4b1e")).toBeTruthy();

    // Press 'r' to reject Satya's item
    fireEvent.keyDown(window, { key: "r" });

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "reject",
        "act-8f4b1e"
      );
    });

    // Item is removed
    await waitFor(() => {
      expect(screen.queryByTestId("pending-card-act-8f4b1e")).toBeNull();
    });
  });

  it("typing inside textarea suppresses hotkeys", () => {
    renderView();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;
    textarea.focus();

    // Dispatch hotkeys targeted at the textarea
    fireEvent.keyDown(textarea, { key: "a" });
    fireEvent.keyDown(textarea, { key: "r" });
    fireEvent.keyDown(textarea, { key: "j" });
    fireEvent.keyDown(textarea, { key: "k" });
    fireEvent.keyDown(textarea, { key: "t" });
    fireEvent.keyDown(textarea, { key: "e" });
    fireEvent.keyDown(textarea, { key: "?" });

    // Ensure no approve or reject actions were triggered
    expect(window.api.executeAction).not.toHaveBeenCalled();
    expect(window.api.rewriteDraft).not.toHaveBeenCalled();

    // Ensure selected item did not change
    expect(screen.getByTestId("target-excerpt").textContent).toContain(
      "Autonomous AI systems in the enterprise"
    );

    // Ensure shortcuts modal did not open
    expect(screen.queryByTestId("keyboard-shortcuts-modal")).toBeNull();
  });

  it("Cmd+Enter inside textarea triggers approve", async () => {
    renderView();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;
    textarea.focus();

    // Press Cmd+Enter inside the editor
    fireEvent.keyDown(textarea, { key: "Enter", metaKey: true });

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "approve",
        "act-8f4b1e",
        expect.any(String)
      );
    });
  });

  it("Ctrl+Enter inside textarea triggers approve", async () => {
    renderView();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;
    textarea.focus();

    // Press Ctrl+Enter inside the editor
    fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

    await waitFor(() => {
      expect(window.api.executeAction).toHaveBeenCalledWith(
        "approve",
        "act-8f4b1e",
        expect.any(String)
      );
    });
  });

  it("? opens the shortcuts modal and Esc closes it", () => {
    renderView();

    // Initially modal is closed
    expect(screen.queryByTestId("keyboard-shortcuts-modal")).toBeNull();

    // Press '?' to open modal
    fireEvent.keyDown(window, { key: "?" });

    expect(screen.getByTestId("keyboard-shortcuts-modal")).toBeTruthy();
    expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();
    expect(screen.getByText("Navigation")).toBeTruthy();
    expect(screen.getByText("Actions")).toBeTruthy();
    expect(screen.getByText("Global")).toBeTruthy();

    // Press 'Escape' to dismiss modal
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("keyboard-shortcuts-modal")).toBeNull();
  });

  it("shortcuts help button in header toggles the cheat sheet modal", () => {
    renderView();

    const helpBtn = screen.getByTestId("shortcuts-help-btn");
    expect(helpBtn).toBeTruthy();

    // Click button to open
    fireEvent.click(helpBtn);
    expect(screen.getByTestId("keyboard-shortcuts-modal")).toBeTruthy();

    // Close using the X button
    const closeBtn = screen.getByTestId("close-shortcuts-modal-btn");
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId("keyboard-shortcuts-modal")).toBeNull();
  });

  it("e focuses draft editor textarea and Escape blurs it", () => {
    renderView();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;
    expect(document.activeElement).not.toBe(textarea);

    // Press 'e'
    fireEvent.keyDown(window, { key: "e" });
    expect(document.activeElement).toBe(textarea);

    // Press 'Escape' while focused
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(document.activeElement).not.toBe(textarea);
  });

  it("t cycles tone quick-pills through technical, inquisitive, contrarian, shorter", async () => {
    renderView();

    const textarea = screen.getByTestId(
      "draft-editor-textarea"
    ) as HTMLTextAreaElement;

    // Press 't' -> 1st tone: technical
    fireEvent.keyDown(window, { key: "t" });
    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "technical"
      );
      expect(textarea.value).toContain("[rewritten with technical]");
    });

    // Press 't' -> 2nd tone: inquisitive
    fireEvent.keyDown(window, { key: "t" });
    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "inquisitive"
      );
      expect(textarea.value).toContain("[rewritten with inquisitive]");
    });

    // Press 't' -> 3rd tone: contrarian
    fireEvent.keyDown(window, { key: "t" });
    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "contrarian"
      );
      expect(textarea.value).toContain("[rewritten with contrarian]");
    });

    // Press 't' -> 4th tone: shorter
    fireEvent.keyDown(window, { key: "t" });
    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "shorter"
      );
      expect(textarea.value).toContain("[rewritten with shorter]");
    });

    // Press 't' again -> cycles back to technical
    fireEvent.keyDown(window, { key: "t" });
    await waitFor(() => {
      expect(window.api.rewriteDraft).toHaveBeenCalledWith(
        expect.any(String),
        "technical"
      );
      expect(textarea.value).toContain("[rewritten with technical]");
    });
  });

  it("modifiers with a and r do not trigger actions", () => {
    renderView();

    // Cmd+A (Select All) should not approve
    fireEvent.keyDown(window, { key: "a", metaKey: true });
    // Ctrl+A should not approve
    fireEvent.keyDown(window, { key: "a", ctrlKey: true });
    // Cmd+R (Reload) should not reject
    fireEvent.keyDown(window, { key: "r", metaKey: true });
    // Ctrl+R should not reject
    fireEvent.keyDown(window, { key: "r", ctrlKey: true });

    expect(window.api.executeAction).not.toHaveBeenCalled();
  });

  it("KeyboardShortcutsModal renders clean dark-tech layout without em-dashes", () => {
    const handleClose = vi.fn();
    const { container } = render(
      <KeyboardShortcutsModal isOpen={true} onClose={handleClose} />
    );

    // Verify modal overlay and container
    expect(screen.getByTestId("keyboard-shortcuts-modal")).toBeTruthy();
    expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

    // Verify zero em-dashes in rendered text
    expect(container.textContent).not.toContain("—");

    // Click backdrop overlay to close
    const overlay = screen.getByTestId("keyboard-shortcuts-modal-overlay");
    fireEvent.click(overlay);
    expect(handleClose).toHaveBeenCalled();
  });
});
