import { useState, useCallback } from "react";
import { ConnectionRequestAction } from "../types";
import { ActionResult } from "../types/api";

export function useConnectionQueue(onMessage?: (msg: string) => void) {
  const [connectionQueue, setConnectionQueue] = useState<ConnectionRequestAction[]>([]);

  const executeConnectionAction = useCallback(
    async (
      action: "approve" | "reject",
      id: string,
      note?: string
    ): Promise<ActionResult> => {
      let result: ActionResult = { success: true, itemId: id, action };
      if (typeof window !== "undefined" && window.api?.executeConnectionAction) {
        try {
          result = await window.api.executeConnectionAction(action, id, note);
        } catch (err: unknown) {
          const errMsg = err instanceof Error ? err.message : "Failed to execute connection action";
          result = { success: false, error: errMsg };
        }
      }

      setConnectionQueue((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                status: action === "approve" ? "approved" : "rejected",
                note_text: note !== undefined ? note : c.note_text,
                approved_at: action === "approve" ? new Date().toISOString() : undefined,
              }
            : c
        )
      );

      const target = connectionQueue.find((c) => c.id === id);
      const name = target ? target.target_name : id;
      onMessage?.(
        action === "approve"
          ? `Connection request approved for ${name}. Invitation queued.`
          : `Connection candidate for ${name} rejected.`
      );

      return result;
    },
    [connectionQueue, onMessage]
  );

  return {
    connectionQueue,
    setConnectionQueue,
    executeConnectionAction,
  };
}
