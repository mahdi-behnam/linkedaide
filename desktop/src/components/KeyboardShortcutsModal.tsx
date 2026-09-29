import React, { useEffect } from "react";
import { Keyboard, X } from "@phosphor-icons/react";

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
      { keys: ["Cmd+Enter", "Ctrl+Enter"], description: "Submit & approve edited draft" },
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        data-testid="keyboard-shortcuts-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
        className="w-full max-w-lg rounded-lg border border-zinc-800 bg-zinc-900 p-5 shadow-2xl transition-all text-zinc-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Keyboard size={18} weight="bold" />
            </div>
            <div>
              <h2
                id="shortcuts-modal-title"
                className="text-sm font-semibold tracking-tight text-zinc-100"
              >
                Keyboard Shortcuts
              </h2>
              <p className="text-[11px] text-zinc-400">
                Approval Queue Power-User Controls
              </p>
            </div>
          </div>
          <button
            type="button"
            data-testid="close-shortcuts-modal-btn"
            onClick={onClose}
            className="rounded-md p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            aria-label="Close shortcuts modal"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {/* Categories Content */}
        <div className="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          {SHORTCUT_CATEGORIES.map((cat) => (
            <div key={cat.title} className="space-y-1.5">
              <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                {cat.title}
              </span>
              <div className="rounded-md border border-zinc-800/80 bg-zinc-950/50 divide-y divide-zinc-800/50">
                {cat.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-3 py-2 text-xs"
                  >
                    <span className="text-zinc-300 font-medium">
                      {item.description}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {item.keys.map((k, kIdx) => (
                        <React.Fragment key={k}>
                          {kIdx > 0 && (
                            <span className="font-mono text-[10px] text-zinc-500">
                              /
                            </span>
                          )}
                          <kbd className="inline-flex min-w-[22px] items-center justify-center rounded border border-zinc-700/60 bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-zinc-200 shadow-sm">
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
        <div className="mt-4 flex items-center justify-between border-t border-zinc-800/80 pt-3 text-[11px] text-zinc-500">
          <span>Single-key shortcuts paused when typing in form fields</span>
          <kbd className="rounded border border-zinc-800 bg-zinc-950 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
            Esc to dismiss
          </kbd>
        </div>
      </div>
    </div>
  );
};
