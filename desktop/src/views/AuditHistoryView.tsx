import React, { useState, useMemo, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { HistoryStatus, AuditEntry } from "../types";
import type { DesktopSettings } from "../types/api";
import {
  MagnifyingGlass,
  Funnel,
  CheckCircle,
  XCircle,
  WarningCircle,
  ArrowSquareOut,
  Copy,
  Check,
  Eye,
  Download,
  X,
} from "../components/icons";

export function buildMediaUrl(
  screenshotPath?: string | null,
  workerUrl?: string | null,
  secret?: string | null
): string {
  if (!screenshotPath) return "";
  if (screenshotPath.startsWith("screenshots/")) {
    const cleanBase = workerUrl ? workerUrl.replace(/\/+$/, "") : "";
    const tokenQuery = secret ? `?token=${encodeURIComponent(secret)}` : "";
    return `${cleanBase}/api/media/${screenshotPath}${tokenQuery}`;
  }
  return screenshotPath;
}

export function getEntryScreenshotPath(entry: AuditEntry): string | undefined {
  return entry.screenshotPath || entry.screenshot_path;
}

export interface AuditHistoryViewProps {
  initialEntries?: AuditEntry[];
}

export const AuditHistoryView: React.FC<AuditHistoryViewProps> = ({ initialEntries }) => {
  const { auditEntries: contextEntries, telemetry } = useApp();
  const auditEntries = initialEntries ?? contextEntries;
  const [settings, setSettings] = useState<DesktopSettings | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);
  const [previewScreenshotEntry, setPreviewScreenshotEntry] = useState<AuditEntry | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedScreenshotKey, setCopiedScreenshotKey] = useState<boolean>(false);
  const [imgLoadError, setImgLoadError] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    const loadSettings = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const loaded = await window.api.getSettings();
          if (isMounted && loaded) {
            setSettings(loaded);
          }
        } catch {
          // ignore background settings retrieval error
        }
      }
    };
    loadSettings();
    return () => {
      isMounted = false;
    };
  }, []);

  const effectiveWorkerUrl =
    settings?.workerUrl || telemetry?.workerUrl || "https://relay.hitl-agent.workers.dev";
  const effectiveSecret = settings?.apiSecret || "";

  const filteredEntries = useMemo(() => {
    return auditEntries.filter((entry) => {
      // Status filter
      if (statusFilter !== "all" && entry.status !== statusFilter) {
        return false;
      }
      // Type filter
      if (typeFilter !== "all" && entry.actionType !== typeFilter) {
        return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = entry.itemId.toLowerCase().includes(q);
        const matchAuthor = entry.targetAuthor?.toLowerCase().includes(q) ?? false;
        const matchDraft = entry.draftExcerpt?.toLowerCase().includes(q) ?? false;
        const matchError = entry.error?.toLowerCase().includes(q) ?? false;
        if (!matchId && !matchAuthor && !matchDraft && !matchError) {
          return false;
        }
      }
      return true;
    });
  }, [auditEntries, statusFilter, typeFilter, searchQuery]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const getStatusBadge = (status: HistoryStatus) => {
    switch (status) {
      case "executed_success":
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium text-tertiary">
            <CheckCircle size={13} weight="bold" />
            <span>Success</span>
          </span>
        );
      case "executed_failed":
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium text-error">
            <XCircle size={13} weight="bold" />
            <span>Failed</span>
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium text-on-surface-variant">
            <XCircle size={13} />
            <span>Rejected</span>
          </span>
        );
      case "expired":
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium text-amber-500">
            <WarningCircle size={13} />
            <span>Expired</span>
          </span>
        );
      case "halted":
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium text-error">
            <WarningCircle size={13} />
            <span>Halted</span>
          </span>
        );
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return isoString;
    }
  };

  const openScreenshotPreview = (entry: AuditEntry) => {
    setImgLoadError(false);
    setCopiedScreenshotKey(false);
    setPreviewScreenshotEntry(entry);
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-5 pb-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center pb-1">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-on-surface">
              Audit History
            </h1>
            <span className="font-mono text-[11px] text-on-surface-variant font-medium">
              ({filteredEntries.length} events)
            </span>
          </div>
          <p className="mt-1 text-xs text-on-surface-variant">
            Append-only verification log of all operator approvals, rejections, and Playwright execution outcomes.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-3">
        <div className="flex flex-1 items-center gap-3">
          {/* Search Box */}
          <div className="relative min-w-[220px] max-w-sm flex-1">
            <MagnifyingGlass
              size={14}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-on-surface-variant"
            />
            <input
              type="text"
              data-testid="audit-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by author, item ID, or draft..."
              className="w-full rounded-md border border-outline-variant/30 bg-surface-container-low py-1.5 pr-3 pl-8 text-xs text-on-surface placeholder:text-on-surface-variant focus:border-primary focus:outline-none"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <Funnel size={14} className="text-on-surface-variant" />
            <select
              data-testid="status-filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-outline-variant/30 bg-surface-container-low px-2.5 py-1.5 font-mono text-xs text-on-surface focus:border-outline focus:outline-none cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="executed_success">Executed Success</option>
              <option value="executed_failed">Executed Failed</option>
              <option value="rejected">Rejected</option>
              <option value="expired">Expired</option>
              <option value="halted">Halted</option>
            </select>
          </div>

          {/* Action Type Filter */}
          <select
            data-testid="type-filter-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-md border border-outline-variant/30 bg-surface-container-low px-2.5 py-1.5 font-mono text-xs text-on-surface focus:border-outline focus:outline-none cursor-pointer"
          >
            <option value="all">All Types</option>
            <option value="comment">Comments</option>
            <option value="post">Posts</option>
          </select>
        </div>

        <span className="font-mono text-[11px] text-on-surface-variant">
          Showing {filteredEntries.length} of {auditEntries.length}
        </span>
      </div>

      {/* Audit Entries Table */}
      <div className="overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-outline-variant/30 bg-surface-container-low font-mono text-[11px] uppercase tracking-wider text-on-surface-variant">
            <tr>
              <th className="px-4 py-2.5">Time</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5">Item ID</th>
              <th className="px-4 py-2.5">Target / Author</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Draft Excerpt</th>
              <th className="px-4 py-2.5 text-right">Proof / Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20">
            {filteredEntries.map((entry) => {
              const shotPath = getEntryScreenshotPath(entry);
              return (
                <tr
                  key={entry.id}
                  data-testid={`audit-row-${entry.id}`}
                  onClick={() => setSelectedEntry(entry)}
                  className="cursor-pointer transition-colors hover:bg-surface-container-low/50"
                >
                  {/* Timestamp */}
                  <td className="px-4 py-2.5 font-mono text-on-surface-variant whitespace-nowrap text-[11px]">
                    {formatDate(entry.decidedAt)}
                  </td>

                  {/* Type */}
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className="font-mono text-[11px] font-medium uppercase text-on-surface-variant">
                      {entry.actionType}
                    </span>
                  </td>

                  {/* Item ID */}
                  <td className="px-4 py-2.5 whitespace-nowrap font-mono text-on-surface text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <span>{entry.itemId}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard(entry.itemId);
                        }}
                        title="Copy item ID"
                        className="text-on-surface-variant hover:text-on-surface cursor-pointer"
                      >
                        {copiedId === entry.itemId ? (
                          <Check size={12} className="text-tertiary" />
                        ) : (
                          <Copy size={12} />
                        )}
                      </button>
                    </div>
                  </td>

                  {/* Target / Author */}
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <div className="max-w-[160px] truncate font-medium text-on-surface text-[12px]">
                      {entry.targetAuthor || "Self Post"}
                    </div>
                    {entry.targetHeadline && (
                      <div className="max-w-[160px] truncate text-[11px] text-on-surface-variant">
                        {entry.targetHeadline}
                      </div>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {getStatusBadge(entry.status)}
                  </td>

                  {/* Draft Excerpt */}
                  <td className="max-w-xs truncate px-4 py-2.5 text-on-surface-variant text-[12px]">
                    {entry.error ? (
                      <span className="text-error font-medium">Error: {entry.error}</span>
                    ) : (
                      entry.draftExcerpt
                    )}
                  </td>

                  {/* Proof Screenshot / Inspect Action */}
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-2">
                      {shotPath && (
                        <button
                          type="button"
                          data-testid={`view-proof-btn-${entry.id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            openScreenshotPreview(entry);
                          }}
                          className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 font-mono text-[11px] font-medium text-primary transition-colors hover:border-primary/50 hover:bg-primary/20 cursor-pointer"
                          title="View Proof Screenshot"
                        >
                          <Eye size={12} weight="bold" />
                          <span>View Proof Screenshot</span>
                        </button>
                      )}
                      <button
                        type="button"
                        data-testid={`inspect-btn-${entry.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEntry(entry);
                        }}
                        className="rounded-md p-1 text-on-surface-variant hover:bg-surface-container hover:text-on-surface cursor-pointer"
                        title="Inspect details"
                      >
                        <ArrowSquareOut size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}

            {filteredEntries.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-xs text-on-surface-variant">
                  No audit log entries match the selected filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Selected Entry Detail Modal / Inspector Drawer */}
      {selectedEntry && (
        <div
          data-testid="audit-detail-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-xl rounded-xl border border-outline bg-surface-container-lowest p-5 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-on-surface">
                    Audit Record Details
                  </h3>
                  {getStatusBadge(selectedEntry.status)}
                </div>
                <p className="mt-1 font-mono text-xs text-on-surface-variant">
                  Item ID: {selectedEntry.itemId}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="rounded-md border border-outline-variant/30 bg-surface-container px-2 py-0.5 text-xs text-on-surface-variant hover:text-on-surface cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="mt-4 space-y-2.5 font-mono text-xs">
              <div className="flex justify-between border-b border-outline-variant/20 pb-2">
                <span className="text-on-surface-variant">Action Type</span>
                <span className="text-on-surface uppercase font-medium">{selectedEntry.actionType}</span>
              </div>
              <div className="flex justify-between border-b border-outline-variant/20 pb-2">
                <span className="text-on-surface-variant">Decision Timestamp</span>
                <span className="text-on-surface">{selectedEntry.decidedAt}</span>
              </div>
              {selectedEntry.executedAt && (
                <div className="flex justify-between border-b border-outline-variant/20 pb-2">
                  <span className="text-on-surface-variant">Execution Timestamp</span>
                  <span className="text-on-surface">{selectedEntry.executedAt}</span>
                </div>
              )}
              {getEntryScreenshotPath(selectedEntry) && (
                <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2">
                  <span className="text-on-surface-variant">Proof Screenshot</span>
                  <button
                    type="button"
                    data-testid={`modal-view-proof-btn-${selectedEntry.id}`}
                    onClick={() => openScreenshotPreview(selectedEntry)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-medium text-primary transition-colors hover:border-primary/50 hover:bg-primary/20 cursor-pointer"
                  >
                    <Eye size={12} weight="bold" />
                    <span>View Proof Screenshot</span>
                  </button>
                </div>
              )}
              {selectedEntry.targetAuthor && (
                <div className="flex justify-between border-b border-outline-variant/20 pb-2">
                  <span className="text-on-surface-variant">Target Author</span>
                  <span className="text-on-surface">{selectedEntry.targetAuthor}</span>
                </div>
              )}
              {selectedEntry.targetUrl && (
                <div className="flex justify-between border-b border-outline-variant/20 pb-2">
                  <span className="text-on-surface-variant">Target Post URL</span>
                  <a
                    href={selectedEntry.targetUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="max-w-xs truncate text-primary hover:underline"
                  >
                    {selectedEntry.targetUrl}
                  </a>
                </div>
              )}
              {selectedEntry.error && (
                <div className="rounded-md border border-error/20 bg-error-container/20 p-2.5 text-error">
                  <p className="font-semibold">Execution Failure:</p>
                  <p className="mt-1">{selectedEntry.error}</p>
                </div>
              )}
              {selectedEntry.draftExcerpt && (
                <div className="pt-2">
                  <span className="text-on-surface-variant">Draft Content:</span>
                  <div className="mt-1 rounded-md border border-outline-variant/30 bg-surface-container-low p-3 font-sans text-xs leading-relaxed text-on-surface">
                    {selectedEntry.draftExcerpt}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Interactive Screenshot Preview Modal */}
      {previewScreenshotEntry && (() => {
        const shotKey = getEntryScreenshotPath(previewScreenshotEntry) || "";
        const mediaUrl = buildMediaUrl(shotKey, effectiveWorkerUrl, effectiveSecret);

        return (
          <div
            data-testid="screenshot-preview-modal"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            onClick={() => setPreviewScreenshotEntry(null)}
          >
            <div
              className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-outline bg-surface-container-lowest shadow-2xl overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b border-outline-variant/30 bg-surface-container px-5 py-3.5">
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
                    <Eye size={16} weight="bold" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold tracking-tight text-on-surface">
                        Execution Proof Screenshot
                      </h3>
                      <span className="rounded-[4px] bg-surface-container-highest px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase text-on-surface">
                        {previewScreenshotEntry.actionType}
                      </span>
                      {getStatusBadge(previewScreenshotEntry.status)}
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-on-surface-variant">
                      Item: {previewScreenshotEntry.itemId}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  data-testid="close-screenshot-modal-btn"
                  onClick={() => setPreviewScreenshotEntry(null)}
                  className="flex items-center gap-1.5 rounded-md border border-outline-variant/30 bg-surface-container-highest px-2.5 py-1 font-mono text-xs text-on-surface-variant transition-colors hover:text-on-surface cursor-pointer"
                >
                  <X size={13} weight="bold" />
                  <span>Close</span>
                </button>
              </div>

              {/* Modal Metadata Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/30 bg-surface-container-low px-5 py-2 font-mono text-xs">
                <div className="flex flex-wrap items-center gap-4 text-on-surface-variant text-[11px]">
                  <div>
                    <span className="text-on-surface-variant">Timestamp: </span>
                    <span className="text-on-surface font-medium">
                      {previewScreenshotEntry.executedAt || previewScreenshotEntry.decidedAt}
                    </span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant">Key: </span>
                    <span className="text-on-surface">{shotKey}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    data-testid="copy-screenshot-key-btn"
                    onClick={() => {
                      navigator.clipboard?.writeText(shotKey);
                      setCopiedScreenshotKey(true);
                      setTimeout(() => setCopiedScreenshotKey(false), 2000);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-md border border-outline-variant/30 bg-surface-container px-2 py-0.5 text-xs text-on-surface transition-colors hover:bg-surface-container-high cursor-pointer"
                  >
                    {copiedScreenshotKey ? (
                      <>
                        <CheckCircle size={12} weight="bold" className="text-tertiary" />
                        <span className="text-tertiary font-medium">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        <span>Copy Key</span>
                      </>
                    )}
                  </button>
                  <a
                    href={mediaUrl}
                    download={shotKey.split("/").pop() || "screenshot.png"}
                    target="_blank"
                    rel="noreferrer"
                    data-testid="download-screenshot-btn"
                    className="inline-flex items-center gap-1.5 rounded-md border border-outline-variant/30 bg-surface-container px-2 py-0.5 text-xs text-on-surface transition-colors hover:bg-surface-container-high"
                  >
                    <Download size={12} weight="bold" />
                    <span>Download</span>
                  </a>
                </div>
              </div>

              {/* Modal Image Viewport */}
              <div className="flex flex-1 items-center justify-center overflow-auto bg-surface-container-lowest p-6 min-h-[360px]">
                {imgLoadError ? (
                  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-outline-variant/30 bg-surface-container-low p-8 text-center">
                    <WarningCircle size={28} className="text-amber-500" />
                    <p className="mt-2 text-xs font-medium text-on-surface">
                      Remote image preview failed to load from R2 vault.
                    </p>
                    <p className="mt-1 font-mono text-[11px] text-on-surface-variant max-w-md break-all">
                      URL: {mediaUrl}
                    </p>
                    <p className="mt-2 font-mono text-[11px] text-on-surface-variant">
                      Local path fallback: {shotKey}
                    </p>
                  </div>
                ) : (
                  <img
                    src={mediaUrl}
                    alt={`Audit proof screenshot for ${previewScreenshotEntry.itemId}`}
                    data-testid="screenshot-modal-image"
                    onError={() => setImgLoadError(true)}
                    className="max-h-[62vh] w-auto max-w-full rounded-md border border-outline-variant/30 object-contain shadow-md"
                  />
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
