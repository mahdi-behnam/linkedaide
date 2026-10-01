import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { AuditHistoryView, buildMediaUrl } from "../src/views/AuditHistoryView";
import { AuditEntry } from "../src/types";

const fixtureAuditEntries: AuditEntry[] = [
  {
    id: "hist-001",
    itemId: "act-8f4b1e",
    actionType: "comment",
    status: "executed_success",
    decidedAt: "2026-09-30T10:00:00Z",
    executedAt: "2026-09-30T10:02:00Z",
    targetAuthor: "Dr. Evelyn Reed",
    targetHeadline: "VP of Distributed Systems",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:998877",
    draftExcerpt: "Deterministic checkpoints ensure replayability across runs.",
    screenshotPath: "screenshots/success_comment_act-8f4b1e.png",
  },
  {
    id: "hist-002",
    itemId: "act-7c2a9f",
    actionType: "post",
    status: "rejected",
    decidedAt: "2026-09-29T14:20:00Z",
    targetAuthor: "Self Post",
    draftExcerpt: "Exploring speculative decoding in production pipelines.",
  },
];

describe("AuditHistoryView & R2 Media Vault", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("buildMediaUrl URL construction", () => {
    it("constructs full remote R2 media URL with token when screenshot begins with screenshots/", () => {
      const url = buildMediaUrl(
        "screenshots/success_comment_123.png",
        "https://relay.hitl-agent.workers.dev",
        "secret-token-456"
      );
      expect(url).toBe(
        "https://relay.hitl-agent.workers.dev/api/media/screenshots/success_comment_123.png?token=secret-token-456"
      );
    });

    it("handles trailing slash in workerUrl cleanly", () => {
      const url = buildMediaUrl(
        "screenshots/success_post_789.png",
        "https://relay.hitl-agent.workers.dev/",
        "secret-token-456"
      );
      expect(url).toBe(
        "https://relay.hitl-agent.workers.dev/api/media/screenshots/success_post_789.png?token=secret-token-456"
      );
    });

    it("omits token query param when secret is absent or empty", () => {
      const url = buildMediaUrl(
        "screenshots/success_comment_123.png",
        "https://relay.hitl-agent.workers.dev",
        ""
      );
      expect(url).toBe(
        "https://relay.hitl-agent.workers.dev/api/media/screenshots/success_comment_123.png"
      );
    });

    it("returns local path directly when path does not begin with screenshots/", () => {
      const localPath = "debug/screenshots/local_screenshot.png";
      const url = buildMediaUrl(
        localPath,
        "https://relay.hitl-agent.workers.dev",
        "secret-token-456"
      );
      expect(url).toBe(localPath);
    });

    it("returns empty string when screenshotPath is null or undefined", () => {
      expect(buildMediaUrl(null, "https://relay.hitl-agent.workers.dev")).toBe("");
      expect(buildMediaUrl(undefined, "https://relay.hitl-agent.workers.dev")).toBe("");
    });
  });

  describe("AuditHistoryView rendering and interactive modal", () => {
    const renderAuditHistory = (initialEntries?: AuditEntry[]) => {
      return render(
        <AppProvider>
          <AuditHistoryView initialEntries={initialEntries ?? fixtureAuditEntries} />
        </AppProvider>
      );
    };

    it("renders empty state cleanly when no audit entries exist", () => {
      renderAuditHistory([]);
      expect(screen.getByText("Audit History")).toBeTruthy();
      expect(screen.getByText("Showing 0 of 0")).toBeTruthy();
      expect(
        screen.getByText("No audit log entries match the selected filters.")
      ).toBeTruthy();
    });

    it("renders the Audit History title and table rows", () => {
      renderAuditHistory();
      expect(screen.getByText("Audit History")).toBeTruthy();
      expect(screen.getByTestId("audit-search-input")).toBeTruthy();
      expect(screen.getByTestId("status-filter-select")).toBeTruthy();
      expect(screen.getByTestId("type-filter-select")).toBeTruthy();
    });

    it("displays View Proof Screenshot button for entries with screenshots", () => {
      renderAuditHistory();
      // hist-001 has screenshotPath configured in initial mock data
      const proofBtn = screen.getByTestId("view-proof-btn-hist-001");
      expect(proofBtn).toBeTruthy();
      expect(proofBtn.textContent).toContain("View Proof Screenshot");

      // hist-002 has no screenshot, so button should not exist
      expect(screen.queryByTestId("view-proof-btn-hist-002")).toBeNull();
    });

    it("opens interactive screenshot preview modal when clicking View Proof Screenshot", async () => {
      renderAuditHistory();
      const proofBtn = screen.getByTestId("view-proof-btn-hist-001");
      fireEvent.click(proofBtn);

      // Modal appears
      const modal = await screen.findByTestId("screenshot-preview-modal");
      expect(modal).toBeTruthy();

      expect(screen.getByText("Execution Proof Screenshot")).toBeTruthy();
      expect(screen.getByText("Item: act-8f4b1e")).toBeTruthy();

      // Check full image preview
      const img = screen.getByTestId("screenshot-modal-image") as HTMLImageElement;
      expect(img).toBeTruthy();
      expect(img.src).toContain(
        "https://relay.hitl-agent.workers.dev/api/media/screenshots/success_comment_act-8f4b1e.png"
      );

      // Check timestamp and key display
      expect(screen.getByText("screenshots/success_comment_act-8f4b1e.png")).toBeTruthy();

      // Check download button
      const downloadBtn = screen.getByTestId("download-screenshot-btn") as HTMLAnchorElement;
      expect(downloadBtn).toBeTruthy();
      expect(downloadBtn.href).toContain(
        "https://relay.hitl-agent.workers.dev/api/media/screenshots/success_comment_act-8f4b1e.png"
      );

      // Close modal
      const closeBtn = screen.getByTestId("close-screenshot-modal-btn");
      fireEvent.click(closeBtn);

      await waitFor(() => {
        expect(screen.queryByTestId("screenshot-preview-modal")).toBeNull();
      });
    });

    it("allows copying screenshot key to clipboard inside the modal", async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: writeTextMock,
        },
        configurable: true,
        writable: true,
      });

      renderAuditHistory();
      const proofBtn = screen.getByTestId("view-proof-btn-hist-001");
      fireEvent.click(proofBtn);

      const copyKeyBtn = await screen.findByTestId("copy-screenshot-key-btn");
      fireEvent.click(copyKeyBtn);

      expect(writeTextMock).toHaveBeenCalledWith("screenshots/success_comment_act-8f4b1e.png");
      expect(screen.getByText("Copied")).toBeTruthy();
    });

    it("opens proof modal from inside the entry detail inspector", async () => {
      renderAuditHistory();
      const inspectBtn = screen.getByTestId("inspect-btn-hist-001");
      fireEvent.click(inspectBtn);

      // Detail modal opens
      expect(screen.getByTestId("audit-detail-modal")).toBeTruthy();
      const modalProofBtn = screen.getByTestId("modal-view-proof-btn-hist-001");
      expect(modalProofBtn).toBeTruthy();

      fireEvent.click(modalProofBtn);

      // Screenshot preview modal opens
      expect(screen.getByTestId("screenshot-preview-modal")).toBeTruthy();
    });
  });
});
