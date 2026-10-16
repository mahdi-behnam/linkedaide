import React, { useState, useMemo, useCallback, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { ConnectionRequestAction } from "../types";
import { UserPlus } from "@phosphor-icons/react";
import { OutreachLeftPane } from "../components/outreach/OutreachLeftPane";
import { OutreachProfileCard } from "../components/outreach/OutreachProfileCard";
import { OutreachNoteStudio, OutreachToneType } from "../components/outreach/OutreachNoteStudio";
import { OutreachSafetyFooter } from "../components/outreach/OutreachSafetyFooter";
import { useDeepNavigation, highlightAndScrollTo } from "../hooks/useDeepNavigation";

export interface OutreachQueueViewProps {
  initialItems?: ConnectionRequestAction[];
}

export const OutreachQueueView: React.FC<OutreachQueueViewProps> = ({ initialItems }) => {
  const {
    connectionQueue: contextQueue,
    executeConnectionAction,
    quota,
    refreshState,
  } = useApp();

  const [items, setItems] = useState<ConnectionRequestAction[]>(
    () => initialItems || contextQueue || []
  );

  useDeepNavigation(
    "outreach",
    useCallback((target) => {
      if (target.itemId) {
        const cleanId = target.itemId.replace(/^outreach-/, "");
        const matched = items.find(
          (i) => i.id === cleanId || i.id === target.itemId
        );
        if (matched) {
          setSelectedId(matched.id);
          setTimeout(() => {
            highlightAndScrollTo(`candidate-card-${matched.id}`);
          }, 120);
        }
      }
    }, [items])
  );

  const [isRefreshing, setIsRefreshing] = useState(false);

  // Synchronize internal items whenever initialItems or contextQueue updates
  useEffect(() => {
    if (initialItems) {
      setItems(initialItems);
    } else if (contextQueue) {
      setItems(contextQueue);
    }
  }, [initialItems, contextQueue]);

  const [selectedId, setSelectedId] = useState<string>(() => {
    const list = initialItems || contextQueue || [];
    return list.length > 0 ? list[0].id : "";
  });

  // Ensure selectedId stays aligned when item list changes
  useEffect(() => {
    if (!selectedId && items.length > 0) {
      setSelectedId(items[0].id);
    } else if (selectedId && !items.some((i) => i.id === selectedId) && items.length > 0) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const selectedCandidate = useMemo(() => {
    return items.find((item) => item.id === selectedId) || items[0] || null;
  }, [items, selectedId]);

  const [notes, setNotes] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    const list = initialItems || contextQueue || [];
    for (const item of list) {
      map[item.id] = item.note_text || "";
    }
    return map;
  });

  // Sync newly added candidate notes
  useEffect(() => {
    setNotes((prev) => {
      const next = { ...prev };
      for (const item of items) {
        if (next[item.id] === undefined) {
          next[item.id] = item.note_text || "";
        }
      }
      return next;
    });
  }, [items]);

  const handleRefresh = useCallback(async () => {
    if (isRefreshing || !refreshState) return;
    setIsRefreshing(true);
    try {
      await refreshState();
    } finally {
      setIsRefreshing(false);
    }
  }, [isRefreshing, refreshState]);

  const currentNote = selectedCandidate
    ? notes[selectedCandidate.id] ?? selectedCandidate.note_text ?? ""
    : "";

  const handleNoteChange = useCallback((text: string) => {
    if (!selectedCandidate) return;
    setNotes((prev) => ({
      ...prev,
      [selectedCandidate.id]: text,
    }));
  }, [selectedCandidate]);

  const handleToneSelect = useCallback(async (tone: OutreachToneType) => {
    if (!selectedCandidate) return;
    const name = selectedCandidate.target_name.split(" ")[0] || "there";
    const context = selectedCandidate.mutual_context || "your recent post";

    let rewritten = "";
    if (tone === "casual") {
      rewritten = `Hey ${name}, loved your recent insights on ${context.toLowerCase().replace(/^commented on /i, "")}. Would be great to connect and stay in touch!`;
    } else if (tone === "technical") {
      rewritten = `Hi ${name}, great discussion regarding ${context.toLowerCase().replace(/^commented on /i, "")}. We are exploring similar architecture tradeoffs and I would value connecting.`;
    } else if (tone === "concise") {
      rewritten = `Hi ${name}, following your work on distributed systems. Would love to connect here on LinkedIn.`;
    }

    if (typeof window !== "undefined" && window.api?.rewriteDraft) {
      try {
        const apiRewritten = await window.api.rewriteDraft(currentNote || rewritten, tone);
        if (apiRewritten && apiRewritten.trim()) {
          rewritten = apiRewritten;
        }
      } catch {
        // Fallback to local tone template
      }
    }

    if (rewritten.length > 300) {
      rewritten = rewritten.slice(0, 300);
    }
    handleNoteChange(rewritten);
  }, [selectedCandidate, currentNote, handleNoteChange]);

  const [isProcessing, setIsProcessing] = useState(false);

  const handleApprove = useCallback(async () => {
    if (!selectedCandidate || currentNote.length > 300 || isProcessing) return;
    setIsProcessing(true);
    try {
      const noteToSend = notes[selectedCandidate.id] ?? selectedCandidate.note_text ?? "";
      await executeConnectionAction("approve", selectedCandidate.id, noteToSend);
      setItems((prev) =>
        prev.map((c) =>
          c.id === selectedCandidate.id
            ? { ...c, status: "approved", note_text: noteToSend, approved_at: new Date().toISOString() }
            : c
        )
      );
    } finally {
      setIsProcessing(false);
    }
  }, [selectedCandidate, currentNote, isProcessing, notes, executeConnectionAction]);

  const handleReject = useCallback(async () => {
    if (!selectedCandidate || isProcessing) return;
    setIsProcessing(true);
    try {
      await executeConnectionAction("reject", selectedCandidate.id);
      setItems((prev) =>
        prev.map((c) =>
          c.id === selectedCandidate.id
            ? { ...c, status: "rejected" }
            : c
        )
      );
    } finally {
      setIsProcessing(false);
    }
  }, [selectedCandidate, isProcessing, executeConnectionAction]);

  const connectionsSent = quota?.connectionsSent ?? 0;
  const connectionsMax = quota?.connectionsMax ?? 10;

  return (
    <div className="flex h-[calc(100vh-2.75rem)] -m-5 overflow-hidden bg-surface text-on-surface">
      {/* Left Column: Candidate List Pane */}
      <OutreachLeftPane
        items={items}
        selectedId={selectedId}
        onSelectId={(id) => setSelectedId(id)}
        connectionsSent={connectionsSent}
        connectionsMax={connectionsMax}
        onRefresh={refreshState ? handleRefresh : undefined}
        isRefreshing={isRefreshing}
      />

      {/* Right Column: Candidate Inspector & Note Studio */}
      <main className="flex-1 flex flex-col bg-surface overflow-y-auto min-w-0">
        {selectedCandidate ? (
          <div className="w-full max-w-[760px] mx-auto px-8 py-8 flex flex-col gap-6">
            {/* Candidate Profile Overview */}
            <OutreachProfileCard candidate={selectedCandidate} />

            {/* 300-Character Note Studio */}
            <OutreachNoteStudio
              candidate={selectedCandidate}
              noteText={currentNote}
              onNoteChange={handleNoteChange}
              onToneSelect={handleToneSelect}
              onApprove={handleApprove}
              onReject={handleReject}
              isProcessing={isProcessing}
            />

            {/* Safety & Rate Limits Footer */}
            <OutreachSafetyFooter
              connectionsSent={connectionsSent}
              connectionsMax={connectionsMax}
            />
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center p-12 text-center text-on-surface-variant">
            <UserPlus size={36} className="opacity-40" />
            <p className="mt-2 text-sm font-medium text-on-surface">
              Select a candidate on the left to inspect details
            </p>
          </div>
        )}
      </main>
    </div>
  );
};
