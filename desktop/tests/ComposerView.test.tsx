import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppProvider } from "../src/context/AppContext";
import { ComposerView } from "../src/views/ComposerView";

describe("ComposerView", () => {
  const renderComposer = () => {
    return render(
      <AppProvider>
        <ComposerView />
      </AppProvider>
    );
  };

  it("renders Post Composer Studio header and inputs", () => {
    renderComposer();
    expect(screen.getByText("Post Composer Studio")).toBeTruthy();
    expect(screen.getByTestId("post-headline-input")).toBeTruthy();
    expect(screen.getByTestId("topic-pillar-select")).toBeTruthy();
    expect(screen.getByTestId("post-content-editor")).toBeTruthy();
  });

  it("updates real-time character, word, and reading time counters as user types", () => {
    renderComposer();
    const editor = screen.getByTestId("post-content-editor");
    const charCounter = screen.getByTestId("char-counter");
    const wordCounter = screen.getByTestId("word-counter");
    const readingTime = screen.getByTestId("reading-time");

    expect(charCounter.textContent).toContain("0 / 3000 chars");
    expect(wordCounter.textContent).toContain("0 words");
    expect(readingTime.textContent).toContain("< 1 min read");

    fireEvent.change(editor, {
      target: {
        value: "Testing autonomous agent workflows with deterministic state machines and human in the loop verification.",
      },
    });

    expect(charCounter.textContent).toContain("104 / 3000 chars");
    expect(wordCounter.textContent).toContain("14 words");
  });

  it("displays above-the-fold 140-character cutoff indicator and fold status", () => {
    renderComposer();
    const editor = screen.getByTestId("post-content-editor");
    const foldBadge = screen.getByTestId("fold-status-badge");

    // Initially 0 chars, 140 remaining
    expect(foldBadge.textContent).toContain("140 chars remaining in fold");
    expect(screen.queryByTestId("visual-fold-line")).toBeNull();

    // Type text exceeding 140 characters
    const longText =
      "Most engineering teams are building agent workflows completely wrong: they rely on autonomous ReAct loops instead of deterministic state machines. This sentence easily crosses the 140 character mobile fold cutoff barrier.";
    fireEvent.change(editor, { target: { value: longText } });

    // Should indicate chars below fold and render visual fold line
    expect(screen.getByTestId("fold-status-badge").textContent).toContain("below fold (...see more)");
    expect(screen.getByTestId("visual-fold-line")).toBeTruthy();
  });

  it("renders AI Hook Studio with all 5 hook archetypes and applies them to editor", () => {
    renderComposer();
    expect(screen.getByText("AI Hook Studio")).toBeTruthy();

    const contrarianBtn = screen.getByTestId("hook-btn-contrarian");
    const dataBtn = screen.getByTestId("hook-btn-data_shock");
    const storyBtn = screen.getByTestId("hook-btn-micro_story");
    const frameworkBtn = screen.getByTestId("hook-btn-framework");
    const synthesisBtn = screen.getByTestId("hook-btn-synthesis");

    expect(contrarianBtn).toBeTruthy();
    expect(dataBtn).toBeTruthy();
    expect(storyBtn).toBeTruthy();
    expect(frameworkBtn).toBeTruthy();
    expect(synthesisBtn).toBeTruthy();

    // Apply Contrarian Stance hook
    fireEvent.click(contrarianBtn);
    const editor = screen.getByTestId("post-content-editor") as HTMLTextAreaElement;
    expect(editor.value).toContain("Most engineering teams are building agent workflows completely wrong:");
    expect(screen.getByTestId("composer-feedback")).toBeTruthy();

    // Switch hook to Data Shock
    fireEvent.click(dataBtn);
    expect(editor.value).toContain("93% of LLM production incidents are not hallucination errors");
  });

  it("handles Carousel PDF previewer with multi-slide navigation and media removal", () => {
    if (!window.URL.createObjectURL) {
      window.URL.createObjectURL = vi.fn(() => "blob:test-pdf-url");
    } else {
      vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:test-pdf-url");
    }

    renderComposer();

    // Dropzone initially visible
    expect(screen.getByTestId("media-dropzone")).toBeTruthy();

    // Attach PDF via file input
    const fileInput = screen.getByTestId("media-file-input");
    const testFile = new File(["sample pdf binary"], "architecture-guide.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(fileInput, { target: { files: [testFile] } });

    // Dropzone replaced by slide viewer
    expect(screen.queryByTestId("media-dropzone")).toBeNull();
    const slideIndicator = screen.getByTestId("slide-indicator");
    expect(slideIndicator.textContent).toContain("Slide 1 of 5");

    const prevBtn = screen.getByTestId("prev-slide-btn");
    const nextBtn = screen.getByTestId("next-slide-btn");

    // Prev disabled on slide 1
    expect(prevBtn.getAttribute("disabled")).not.toBeNull();

    // Navigate to slide 2
    fireEvent.click(nextBtn);
    expect(slideIndicator.textContent).toContain("Slide 2 of 5");

    // Navigate back to slide 1
    fireEvent.click(prevBtn);
    expect(slideIndicator.textContent).toContain("Slide 1 of 5");

    // Remove media
    const removeBtn = screen.getByTestId("remove-media-btn");
    fireEvent.click(removeBtn);
    expect(screen.getByTestId("media-dropzone")).toBeTruthy();
  });

  it("allows saving draft and scheduling post via the scheduling bar", () => {
    renderComposer();
    const editor = screen.getByTestId("post-content-editor");
    const headlineInput = screen.getByTestId("post-headline-input");
    const saveDraftBtn = screen.getByTestId("save-draft-btn");
    const scheduleBtn = screen.getByTestId("schedule-post-btn");

    // Attempt save draft when empty
    fireEvent.click(saveDraftBtn);
    expect(screen.getByTestId("composer-feedback").textContent).toContain("Please add post text before saving draft.");

    // Fill in content
    fireEvent.change(headlineInput, { target: { value: "HITL Production Rules" } });
    fireEvent.change(editor, { target: { value: "3 safety invariants we enforce in every agent workflow." } });

    // Save draft
    fireEvent.click(saveDraftBtn);
    expect(screen.getByTestId("composer-feedback").textContent).toContain("Draft saved successfully.");

    // Schedule post
    const dateInput = screen.getByTestId("schedule-date-input");
    fireEvent.change(dateInput, { target: { value: "2026-10-05" } });
    fireEvent.click(scheduleBtn);
    expect(screen.getByTestId("composer-feedback").textContent).toContain("Post scheduled successfully.");
  });

  it("invokes uploadMedia IPC bridge when uploading media to vault", async () => {
    const uploadMediaMock = vi.fn().mockResolvedValue({
      success: true,
      key: "posts/doc-123.pdf",
      url: "https://worker.dev/api/media/posts/doc-123.pdf?token=abc",
    });
    window.api = {
      ...(window.api || {}),
      uploadMedia: uploadMediaMock,
    } as any;

    renderComposer();
    const fileInput = screen.getByTestId("media-file-input");
    const testFile = new File(["pdf contents"], "strategy.pdf", { type: "application/pdf" });
    testFile.arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(12));

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(uploadMediaMock).toHaveBeenCalledWith(
        "strategy.pdf",
        expect.any(ArrayBuffer),
        "application/pdf"
      );
    });
  });
});
