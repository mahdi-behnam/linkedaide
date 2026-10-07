export const isMac =
  typeof window !== "undefined" &&
  ((window as any).api?.platform === "darwin" ||
    (typeof navigator !== "undefined" &&
      (navigator.platform?.toLowerCase().includes("mac") ||
        navigator.userAgent?.toLowerCase().includes("mac"))));

export const cmdOrCtrl = isMac ? "⌘" : "Ctrl";
export const cmdOrCtrlName = isMac ? "Cmd" : "Ctrl";

export function formatKeyCombo(key: string, glue: string = ""): string {
  return isMac ? `⌘${glue}${key}` : `Ctrl+${key}`;
}
