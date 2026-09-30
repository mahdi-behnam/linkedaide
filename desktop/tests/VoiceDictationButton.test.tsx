import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { VoiceDictationButton } from "../src/components/VoiceDictationButton";

class MockSpeechRecognition {
  static instances: MockSpeechRecognition[] = [];
  continuous = false;
  interimResults = false;
  lang = "";
  onstart: (() => void) | null = null;
  onresult: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onend: (() => void) | null = null;

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start = vi.fn(() => {
    if (this.onstart) {
      this.onstart();
    }
  });

  stop = vi.fn(() => {
    if (this.onend) {
      this.onend();
    }
  });

  abort = vi.fn(() => {
    if (this.onend) {
      this.onend();
    }
  });
}

describe("VoiceDictationButton", () => {
  const originalSpeechRecognition = (window as any).SpeechRecognition;
  const originalWebkitSpeechRecognition = (window as any).webkitSpeechRecognition;

  beforeEach(() => {
    MockSpeechRecognition.instances = [];
  });

  afterEach(() => {
    (window as any).SpeechRecognition = originalSpeechRecognition;
    (window as any).webkitSpeechRecognition = originalWebkitSpeechRecognition;
    vi.restoreAllMocks();
  });

  it("renders graceful fallback tooltip notice when speech recognition is unavailable", () => {
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;

    const onTranscript = vi.fn();
    render(<VoiceDictationButton onTranscript={onTranscript} />);

    const button = screen.getByTestId("voice-dictation-btn");
    expect(button).toBeTruthy();
    expect(button.getAttribute("aria-label")).toContain("Unsupported");

    // Click shows notice
    fireEvent.click(button);
    expect(screen.getByTestId("unsupported-notice")).toBeTruthy();
    expect(
      screen.getByText("Speech recognition not available in this environment")
    ).toBeTruthy();
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("renders idle state with Microphone icon when supported", () => {
    (window as any).SpeechRecognition = MockSpeechRecognition;

    const onTranscript = vi.fn();
    render(<VoiceDictationButton onTranscript={onTranscript} />);

    const button = screen.getByTestId("voice-dictation-btn");
    expect(button).toBeTruthy();
    expect(button.getAttribute("data-recording")).toBe("false");
    expect(screen.getByText("Dictate")).toBeTruthy();
  });

  it("toggles recording on click and calls speech recognition start/stop", () => {
    (window as any).SpeechRecognition = MockSpeechRecognition;

    const onTranscript = vi.fn();
    render(<VoiceDictationButton onTranscript={onTranscript} />);

    const button = screen.getByTestId("voice-dictation-btn");

    // Click to start
    fireEvent.click(button);
    expect(button.getAttribute("data-recording")).toBe("true");
    expect(screen.getByText("Listening...")).toBeTruthy();
    expect(MockSpeechRecognition.instances.length).toBe(1);
    expect(MockSpeechRecognition.instances[0].start).toHaveBeenCalled();

    // Click to stop
    fireEvent.click(button);
    expect(button.getAttribute("data-recording")).toBe("false");
    expect(MockSpeechRecognition.instances[0].stop).toHaveBeenCalled();
  });

  it("extracts recognized transcript and invokes onTranscript callback", () => {
    (window as any).SpeechRecognition = MockSpeechRecognition;

    const onTranscript = vi.fn();
    render(<VoiceDictationButton onTranscript={onTranscript} />);

    const button = screen.getByTestId("voice-dictation-btn");
    fireEvent.click(button);

    const recognition = MockSpeechRecognition.instances[0];
    expect(recognition).toBeTruthy();

    act(() => {
      if (recognition.onresult) {
        recognition.onresult({
          resultIndex: 0,
          results: [
            [
              {
                transcript: "Deterministic guardrails outperform raw scale",
              },
            ],
          ],
        });
      }
    });

    expect(onTranscript).toHaveBeenCalledWith(
      "Deterministic guardrails outperform raw scale"
    );
  });

  it("handles controlled isRecording prop changes", () => {
    (window as any).SpeechRecognition = MockSpeechRecognition;

    const onTranscript = vi.fn();
    const { rerender } = render(
      <VoiceDictationButton onTranscript={onTranscript} isRecording={false} />
    );

    const button = screen.getByTestId("voice-dictation-btn");
    expect(button.getAttribute("data-recording")).toBe("false");

    rerender(
      <VoiceDictationButton onTranscript={onTranscript} isRecording={true} />
    );
    expect(button.getAttribute("data-recording")).toBe("true");
    expect(MockSpeechRecognition.instances[0].start).toHaveBeenCalled();
  });
});
