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
          className={`inline-flex items-center gap-1.5 rounded-md border border-zinc-800/80 bg-zinc-900/30 px-2.5 py-1 text-xs text-zinc-500 cursor-not-allowed opacity-75 transition-colors ${className}`}
        >
          <MicrophoneSlash size={14} className="shrink-0 text-zinc-500" />
          <span className="font-mono text-[10px]">Voice</span>
        </button>
        {showTooltip && (
          <div
            data-testid="unsupported-notice"
            role="tooltip"
            className="absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-[10px] text-zinc-300 shadow-md"
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
        className={`group relative inline-flex items-center gap-1.5 rounded-md border text-xs font-medium transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
          isRecording
            ? "border-emerald-500/60 bg-emerald-500/15 px-2.5 py-1 text-emerald-400 ring-2 ring-emerald-500/30 animate-pulse"
            : "border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-zinc-400 hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200"
        } ${className}`}
      >
        {isRecording && (
          <span className="pointer-events-none absolute -inset-0.5 rounded-md bg-emerald-500/20 opacity-75 animate-ping" />
        )}
        <Microphone
          size={14}
          weight={isRecording ? "fill" : "regular"}
          className={`shrink-0 ${
            isRecording ? "text-emerald-400 animate-pulse" : "text-zinc-400 group-hover:text-zinc-200"
          }`}
        />
        {isRecording ? (
          <>
            <Waveform size={14} className="shrink-0 text-emerald-400 animate-pulse" />
            <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
              Listening...
            </span>
          </>
        ) : (
          <span className="font-mono text-[10px]">Dictate</span>
        )}
      </button>
    </div>
  );
};
