import { useEffect, useCallback, RefObject } from "react";

export interface UseQueueShortcutsOptions {
  items: Array<{ id: string }>;
  selectedId: string | null;
  onSelectId: (id: string) => void;
  onApprove: () => void | Promise<void>;
  onReject: () => void | Promise<void>;
  onCycleTone?: () => void;
  onToggleShortcuts?: () => void;
  onCloseShortcuts?: () => void;
  isShortcutsOpen?: boolean;
  textareaRef?: RefObject<HTMLTextAreaElement | null>;
  queueListRef?: RefObject<HTMLElement | null>;
  disabled?: boolean;
}

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || typeof target !== "object" || !("tagName" in target)) return false;
  const element = target as HTMLElement;
  const tagName = element.tagName?.toLowerCase();
  if (tagName === "textarea") return true;
  if (tagName === "input") {
    const inputType = (element as HTMLInputElement).type?.toLowerCase() || "text";
    return !["button", "checkbox", "radio", "submit", "reset", "range", "color", "file"].includes(inputType);
  }
  if (element.isContentEditable) return true;
  if (typeof element.closest === "function" && Boolean(element.closest("input, textarea, [contenteditable='true']"))) {
    return true;
  }
  return false;
}

export const useQueueShortcuts = ({
  items,
  selectedId,
  onSelectId,
  onApprove,
  onReject,
  onCycleTone,
  onToggleShortcuts,
  onCloseShortcuts,
  isShortcutsOpen = false,
  textareaRef,
  queueListRef,
  disabled = false,
}: UseQueueShortcutsOptions) => {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (disabled) return;

      const isModifierPressed = e.metaKey || e.ctrlKey;

      // 1. Submit & approve draft: Cmd+Enter or Ctrl+Enter (always active even in textarea)
      if (isModifierPressed && e.key === "Enter") {
        e.preventDefault();
        onApprove();
        return;
      }

      // 2. Escape: blur textarea and focus queue list, or close modal if open
      if (e.key === "Escape" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        if (isShortcutsOpen) {
          e.preventDefault();
          if (onCloseShortcuts) {
            onCloseShortcuts();
          } else if (onToggleShortcuts) {
            onToggleShortcuts();
          }
          return;
        }

        const isCurrentElementEditable =
          (textareaRef?.current && document.activeElement === textareaRef.current) ||
          isEditableTarget(document.activeElement) ||
          isEditableTarget(e.target);

        if (isCurrentElementEditable) {
          e.preventDefault();
          if (textareaRef?.current) {
            textareaRef.current.blur();
          } else if (document.activeElement instanceof HTMLElement) {
            document.activeElement.blur();
          }
          queueListRef?.current?.focus();
          return;
        }

        return;
      }

      // Ignore single-letter navigation and action hotkeys while typing in input/textarea/contenteditable
      if (isEditableTarget(e.target) || isEditableTarget(document.activeElement)) {
        return;
      }

      // If shortcuts cheat sheet modal is open, ignore navigation/action hotkeys (except ? to toggle)
      if (isShortcutsOpen) {
        if (e.key === "?" && !isModifierPressed && !e.altKey) {
          e.preventDefault();
          onToggleShortcuts?.();
        }
        return;
      }

      // Disallow navigation and single-key actions when modifier keys are pressed
      if (isModifierPressed || e.altKey) {
        return;
      }

      const key = e.key;

      // Toggle cheat sheet modal: '?'
      if (key === "?") {
        e.preventDefault();
        onToggleShortcuts?.();
        return;
      }

      // Navigation: next item with 'j' or 'ArrowDown'
      if (key === "j" || key === "ArrowDown") {
        e.preventDefault();
        if (items.length === 0) return;
        const currentIndex = items.findIndex((i) => i.id === selectedId);
        if (currentIndex === -1) {
          onSelectId(items[0].id);
        } else if (currentIndex < items.length - 1) {
          onSelectId(items[currentIndex + 1].id);
        }
        return;
      }

      // Navigation: previous item with 'k' or 'ArrowUp'
      if (key === "k" || key === "ArrowUp") {
        e.preventDefault();
        if (items.length === 0) return;
        const currentIndex = items.findIndex((i) => i.id === selectedId);
        if (currentIndex === -1) {
          onSelectId(items[0].id);
        } else if (currentIndex > 0) {
          onSelectId(items[currentIndex - 1].id);
        }
        return;
      }

      // Action: Approve & Queue with 'a'
      if (key.toLowerCase() === "a") {
        e.preventDefault();
        if (selectedId) {
          onApprove();
        }
        return;
      }

      // Action: Reject with 'r'
      if (key.toLowerCase() === "r") {
        e.preventDefault();
        if (selectedId) {
          onReject();
        }
        return;
      }

      // Action: Focus comment draft editor with 'e'
      if (key.toLowerCase() === "e") {
        e.preventDefault();
        if (textareaRef?.current) {
          textareaRef.current.focus();
        }
        return;
      }

      // Action: Cycle tone quick-pills with 't'
      if (key.toLowerCase() === "t") {
        e.preventDefault();
        onCycleTone?.();
        return;
      }
    },
    [
      disabled,
      isShortcutsOpen,
      items,
      selectedId,
      onSelectId,
      onApprove,
      onReject,
      onCycleTone,
      onToggleShortcuts,
      onCloseShortcuts,
      textareaRef,
      queueListRef,
    ]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleKeyDown]);
};
