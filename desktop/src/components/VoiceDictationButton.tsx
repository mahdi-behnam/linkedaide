import React, { useState, useEffect, useRef, useCallback } from "react";
import { Microphone, MicrophoneSlash, Waveform } from "./icons";

export interface VoiceDictationButtonProps {
  onTranscript: (text: string) => void;
  isRecording?: boolean;
  className?: string;
  disabled?: boolean;
}

export const VoiceDictationButton: React.FC<VoiceDictationButtonProps> = ({
  onTranscript,
  isRecording: isRecordingProp,
  className = "",
  disabled = false,
}) => {
  const [isInternalRecording, setIsInternalRecording] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const recognitionRef = useRef<any>(null);

  const isSupported =
    typeof window !== "undefined" &&
    Boolean(
      (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition
    );

  const isRecording =
    isRecordingProp !== undefined ? isRecordingProp : isInternalRecording;

  const stopRecognition = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore errors during stop
      }
      recognitionRef.current = null;
    }
    setIsInternalRecording(false);
  }, []);

  const startRecognition = useCallback(() => {
    if (!isSupported) {
      setShowTooltip(true);
      setTimeout(() => setShowTooltip(false), 3000);
      return;
    }

    try {
      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        setIsInternalRecording(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = "";
        if (event.results) {
          for (let i = event.resultIndex || 0; i < event.results.length; i++) {
            const res = event.results[i];
            if (res && res[0]?.transcript) {
              transcript += res[0].transcript;
            }
          }
        }
        const trimmed = transcript.trim();
        if (trimmed) {
          onTranscript(trimmed);
        }
      };

      recognition.onerror = () => {
        setIsInternalRecording(false);
      };

      recognition.onend = () => {
        setIsInternalRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsInternalRecording(false);
    }
  }, [isSupported, onTranscript]);

  useEffect(() => {
    if (isRecordingProp !== undefined) {
      if (isRecordingProp && !isInternalRecording) {
        startRecognition();
      } else if (!isRecordingProp && isInternalRecording) {
        stopRecognition();
      }
    }
  }, [isRecordingProp, isInternalRecording, startRecognition, stopRecognition]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
      }
    };
  }, []);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (disabled) return;

    if (!isSupported) {
      setShowTooltip(true);
      setTimeout(() => setShowTooltip(false), 3000);
      return;
    }

    if (isRecording) {
      stopRecognition();
    } else {
      startRecognition();
    }
  };

  if (!isSupported) {
    return (
      <div className="relative inline-block">
        <button
          type="button"
          data-testid="voice-dictation-btn"
          aria-label="Voice Dictation (Unsupported)"
          title="Voice dictation unavailable in this environment"
          onClick={handleClick}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          className={`inline-flex items-center gap-1.5 rounded-md border border-outline bg-surface-container-low px-2 py-0.5 text-xs text-on-surface-variant cursor-not-allowed opacity-60 transition-colors ${className}`}
        >
          <MicrophoneSlash size={13} className="shrink-0 text-on-surface-variant" />
          <span className="text-[11px]">Voice</span>
        </button>
        {showTooltip && (
          <div
            data-testid="unsupported-notice"
            role="tooltip"
            className="absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md border border-outline bg-surface-bright px-2 py-1 text-[11px] text-on-surface shadow-md"
          >
            Speech recognition not available in this environment
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        data-testid="voice-dictation-btn"
        data-recording={isRecording ? "true" : "false"}
        aria-label={isRecording ? "Stop voice dictation" : "Start voice dictation"}
        title={isRecording ? "Click to stop dictation" : "Dictate text by voice"}
        onClick={handleClick}
        disabled={disabled}
        className={`group relative inline-flex items-center gap-1.5 rounded-md border text-xs font-medium transition-colors ${
          isRecording
            ? "border-error/40 bg-error/10 px-2 py-0.5 text-error shadow-2xs"
            : "border-outline bg-surface-container-low px-2 py-0.5 text-on-surface-variant hover:border-outline-variant hover:bg-surface-container hover:text-on-surface shadow-2xs"
        } ${className}`}
      >
        <Microphone
          size={13}
          weight={isRecording ? "fill" : "regular"}
          className={`shrink-0 ${
            isRecording ? "text-error" : "text-on-surface-variant group-hover:text-on-surface"
          }`}
        />
        {isRecording ? (
          <>
            <Waveform size={13} className="shrink-0 text-error" />
            <span className="text-[11px] font-medium text-error">
              Listening...
            </span>
          </>
        ) : (
          <span className="text-[11px]">Dictate</span>
        )}
      </button>
    </div>
  );
};
