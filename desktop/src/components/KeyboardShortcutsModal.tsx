import React, { useEffect } from "react";
import { Keyboard, X } from "@phosphor-icons/react";
import { isMac } from "../utils/platform";

export interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutItem {
  keys: string[];
  description: string;
}

interface ShortcutCategory {
  title: string;
  items: ShortcutItem[];
}

const SHORTCUT_CATEGORIES: ShortcutCategory[] = [
  {
    title: "Navigation",
    items: [
      { keys: ["j", "k"], description: "Select next / previous item in queue" },
      { keys: ["Down", "Up"], description: "Select next / previous item in queue" },
    ],
  },
  {
    title: "Actions",
    items: [
      { keys: ["A"], description: "Approve & Queue current item" },
      { keys: ["R"], description: "Reject current item" },
      { keys: ["E"], description: "Focus comment draft editor" },
      { keys: ["T"], description: "Cycle tone quick-pills (technical, inquisitive, contrarian, shorter)" },
      { keys: [isMac ? "Cmd+Enter" : "Ctrl+Enter"], description: "Submit & approve edited draft" },
    ],
  },
  {
    title: "Global",
    items: [
      { keys: ["?"], description: "Toggle keyboard shortcuts cheat sheet" },
      { keys: ["Esc"], description: "Close modal / Blur editor" },
    ],
  },
];

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      data-testid="keyboard-shortcuts-modal-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        data-testid="keyboard-shortcuts-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
        className="w-full max-w-lg rounded-xl border border-outline bg-surface-bright p-5 shadow-2xl transition-all text-on-surface"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-outline pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
              <Keyboard size={16} weight="bold" />
            </div>
            <div>
              <h2
                id="shortcuts-modal-title"
                className="text-sm font-semibold tracking-tight text-on-surface"
              >
                Keyboard Shortcuts
              </h2>
              <p className="text-[11px] text-on-surface-variant">
                Approval Queue Shortcuts
              </p>
            </div>
          </div>
          <button
            type="button"
            data-testid="close-shortcuts-modal-btn"
            onClick={onClose}
            className="rounded-md p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
            aria-label="Close shortcuts modal"
          >
            <X size={15} weight="bold" />
          </button>
        </div>

        {/* Categories Content */}
        <div className="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          {SHORTCUT_CATEGORIES.map((cat) => (
            <div key={cat.title} className="space-y-1.5">
              <span className="font-sans text-[11px] font-semibold text-on-surface-variant">
                {cat.title}
              </span>
              <div className="rounded-lg border border-outline bg-surface-container-lowest divide-y divide-outline/50">
                {cat.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-3 py-2 text-xs"
                  >
                    <span className="text-on-surface font-normal">
                      {item.description}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {item.keys.map((k, kIdx) => (
                        <React.Fragment key={k}>
                          {kIdx > 0 && (
                            <span className="text-[10px] text-on-surface-variant">
                              /
                            </span>
                          )}
                          <kbd className="inline-flex min-w-[20px] items-center justify-center rounded-md border border-outline bg-surface-container-high px-1.5 py-0.5 font-sans text-[11px] font-medium text-on-surface shadow-2xs">
                            {k}
                          </kbd>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer info */}
        <div className="mt-4 flex items-center justify-between border-t border-outline pt-3 text-[11px] text-on-surface-variant">
          <span>Single-key shortcuts paused when typing in form fields</span>
          <kbd className="rounded-md border border-outline bg-surface-container px-1.5 py-0.5 font-sans text-[10px] text-on-surface-variant">
            Esc to dismiss
          </kbd>
        </div>
      </div>
    </div>
  );
};
