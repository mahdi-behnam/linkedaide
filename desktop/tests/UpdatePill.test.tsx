// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UpdatePill } from "../src/components/updater/UpdatePill";

describe("UpdatePill and UpdatePopover", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = {
      updaterGetStatus: vi.fn().mockResolvedValue({
        status: "idle",
        info: null,
        progress: null,
        error: null,
      }),
      onUpdaterEvent: vi.fn(() => {
        return () => {};
      }),
      updaterStartDownload: vi.fn().mockResolvedValue(true),
      updaterCancelDownload: vi.fn().mockResolvedValue(true),
      updaterQuitAndInstall: vi.fn().mockResolvedValue(true),
    };

    (window as any).api = mockApi;
  });

  it("renders nothing when status is idle", async () => {
    render(<UpdatePill />);
    await waitFor(() => {
      expect(mockApi.updaterGetStatus).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("update-pill-button")).toBeNull();
  });

  it("renders Update Available pill and opens popover on click", async () => {
    mockApi.updaterGetStatus.mockResolvedValueOnce({
      status: "available",
      info: {
        version: "1.3.1",
        releaseName: "LinkedAide 1.3.1 - Telemetry Update",
        releaseNotes: "- Live download speed\n- Apple HIG pill",
      },
      progress: null,
      error: null,
    });

    render(<UpdatePill />);

    const pill = await screen.findByTestId("update-pill-button");
    expect(pill).toBeTruthy();
    expect(screen.getByText("Update Available")).toBeTruthy();

    // Click pill to open popover
    fireEvent.click(pill);

    expect(screen.getByTestId("update-popover")).toBeTruthy();
    expect(screen.getByText("v1.3.1")).toBeTruthy();
    expect(screen.getByText("LinkedAide 1.3.1 - Telemetry Update")).toBeTruthy();

    // Trigger download
    const downloadBtn = screen.getByTestId("start-download-btn");
    fireEvent.click(downloadBtn);
    expect(mockApi.updaterStartDownload).toHaveBeenCalled();
  });

  it("renders downloading progress and live telemetry in popover", async () => {
    mockApi.updaterGetStatus.mockResolvedValueOnce({
      status: "downloading",
      info: { version: "1.3.1" },
      progress: {
        percent: 45.2,
        bytesPerSecond: 3.4 * 1024 * 1024,
        transferred: 24.5 * 1024 * 1024,
        total: 54.8 * 1024 * 1024,
        remainingBytes: 30.3 * 1024 * 1024,
        etaSeconds: 9,
      },
      error: null,
    });

    render(<UpdatePill />);

    const pill = await screen.findByTestId("update-pill-button");
    expect(pill.textContent).toContain("Downloading 45%");

    // Click pill to inspect telemetry in popover
    fireEvent.click(pill);

    expect(screen.getByText("45.2%")).toBeTruthy();
    expect(screen.getByText("3.4 MB/s")).toBeTruthy();
    expect(screen.getByText("9s left")).toBeTruthy();

    const cancelBtn = screen.getByTestId("cancel-download-btn");
    fireEvent.click(cancelBtn);
    expect(mockApi.updaterCancelDownload).toHaveBeenCalled();
  });

  it("renders downloaded state and triggers restart on confirmation", async () => {
    mockApi.updaterGetStatus.mockResolvedValueOnce({
      status: "downloaded",
      info: { version: "1.3.1" },
      progress: null,
      error: null,
    });

    render(<UpdatePill />);

    const pill = await screen.findByTestId("update-pill-button");
    expect(pill.textContent).toContain("Restart to Update");

    // Click pill to open restart confirmation
    fireEvent.click(pill);

    expect(screen.getByText("Ready to Install")).toBeTruthy();
    const restartBtn = screen.getByTestId("restart-install-btn");
    fireEvent.click(restartBtn);

    expect(mockApi.updaterQuitAndInstall).toHaveBeenCalled();
  });

  it("renders rich HTML release notes with external links and proper popover min-height", async () => {
    const windowOpenSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    mockApi.updaterGetStatus.mockResolvedValueOnce({
      status: "available",
      info: {
        version: "1.6.0",
        releaseName: "v1.6.0",
        releaseNotes: `<h2><a href="https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0">1.6.0</a> (2026-10-16)</h2>
<h3>Features</h3>
<ul>
<li><strong>desktop:</strong> add fork drift detection (<a href="https://github.com/mahdi-behnam/linkedaide/commit/1234567">1234567</a>)</li>
</ul>`,
      },
      progress: null,
      error: null,
    });

    render(<UpdatePill />);

    const pill = await screen.findByTestId("update-pill-button");
    fireEvent.click(pill);

    // Verify popover container has increased min-height
    const popover = screen.getByTestId("update-popover");
    expect(popover.className).toContain("min-h-[270px]");

    // Verify release notes element
    const notesContainer = screen.getByTestId("update-release-notes");
    expect(notesContainer.className).toContain("min-h-[130px]");
    expect(notesContainer.className).toContain("release-notes-prose");

    // Verify rendered DOM elements, not escaped HTML strings
    expect(notesContainer.querySelector("h2")).toBeTruthy();
    expect(notesContainer.querySelector("h3")?.textContent).toBe("Features");
    expect(notesContainer.querySelector("ul")).toBeTruthy();
    expect(notesContainer.querySelector("li")).toBeTruthy();
    expect(notesContainer.querySelector("strong")?.textContent).toBe("desktop:");

    // Verify links have target="_blank" and rel="noopener noreferrer"
    const compareLink = notesContainer.querySelector('a[href="https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0"]') as HTMLAnchorElement;
    expect(compareLink).toBeTruthy();
    expect(compareLink.getAttribute("target")).toBe("_blank");
    expect(compareLink.getAttribute("rel")).toBe("noopener noreferrer");

    // Click link and verify external browser opening
    fireEvent.click(compareLink);
    expect(windowOpenSpy).toHaveBeenCalledWith(
      "https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0",
      "_blank",
      "noopener,noreferrer",
    );

    windowOpenSpy.mockRestore();
  });
});
