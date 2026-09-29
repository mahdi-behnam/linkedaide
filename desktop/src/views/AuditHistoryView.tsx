import React, { useState, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { HistoryStatus, AuditEntry } from "../types";
import {
  MagnifyingGlass,
  Funnel,
  CheckCircle,
  XCircle,
  WarningCircle,
  ArrowSquareOut,
  Copy,
  Check,
} from "../components/icons";

export const AuditHistoryView: React.FC = () => {
  const { auditEntries } = useApp();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

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
          <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-emerald-400">
            <CheckCircle size={12} weight="bold" />
            <span>Success</span>
          </span>
        );
      case "executed_failed":
        return (
          <span className="inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-rose-400">
            <XCircle size={12} weight="bold" />
            <span>Failed</span>
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 font-mono text-[11px] font-medium text-zinc-400">
            <XCircle size={12} />
            <span>Rejected</span>
          </span>
        );
      case "expired":
        return (
          <span className="inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-amber-400">
            <WarningCircle size={12} />
            <span>Expired</span>
          </span>
        );
      case "halted":
        return (
          <span className="inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-rose-400">
            <WarningCircle size={12} />
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Audit History
            </h1>
            <span className="rounded-full border border-zinc-800 bg-zinc-900/80 px-2.5 py-0.5 font-mono text-xs text-zinc-400">
              {filteredEntries.length} events
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Append-only verification log of all operator approvals, rejections, and Playwright execution outcomes.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
        <div className="flex flex-1 items-center gap-3">
          {/* Search Box */}
          <div className="relative min-w-[220px] max-w-sm flex-1">
            <MagnifyingGlass
              size={14}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-zinc-500"
            />
            <input
              type="text"
              data-testid="audit-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by author, item ID, or draft..."
              className="w-full rounded-md border border-zinc-800 bg-zinc-950 py-1.5 pr-3 pl-8 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <Funnel size={14} className="text-zinc-500" />
            <select
              data-testid="status-filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-300 focus:border-zinc-700 focus:outline-none"
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
            className="rounded-md border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-300 focus:border-zinc-700 focus:outline-none"
          >
            <option value="all">All Types</option>
            <option value="comment">Comments</option>
            <option value="post">Posts</option>
          </select>
        </div>

        <span className="font-mono text-[11px] text-zinc-500">
          Showing {filteredEntries.length} of {auditEntries.length}
        </span>
      </div>

      {/* Audit Entries Table */}
      <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/40">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-zinc-800 bg-zinc-900/80 font-mono text-[11px] uppercase tracking-wider text-zinc-400">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Item ID</th>
              <th className="px-4 py-3">Target / Author</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Draft Excerpt</th>
              <th className="px-4 py-3 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {filteredEntries.map((entry) => (
              <tr
                key={entry.id}
                data-testid={`audit-row-${entry.id}`}
                onClick={() => setSelectedEntry(entry)}
                className="cursor-pointer transition-colors hover:bg-zinc-850/50"
              >
                {/* Timestamp */}
                <td className="px-4 py-3 font-mono text-zinc-400 whitespace-nowrap">
                  {formatDate(entry.decidedAt)}
                </td>

                {/* Type */}
                <td className="px-4 py-3 whitespace-nowrap">
                  <span
                    className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${
                      entry.actionType === "comment"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : "bg-violet-500/10 text-violet-400"
                    }`}
                  >
                    {entry.actionType}
                  </span>
                </td>

                {/* Item ID */}
                <td className="px-4 py-3 whitespace-nowrap font-mono text-zinc-300">
                  <div className="flex items-center gap-1.5">
                    <span>{entry.itemId}</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard(entry.itemId);
                      }}
                      title="Copy item ID"
                      className="text-zinc-500 hover:text-zinc-300"
                    >
                      {copiedId === entry.itemId ? (
                        <Check size={12} className="text-emerald-400" />
                      ) : (
                        <Copy size={12} />
                      )}
                    </button>
                  </div>
                </td>

                {/* Target / Author */}
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="max-w-[160px] truncate font-medium text-zinc-200">
                    {entry.targetAuthor || "Self Post"}
                  </div>
                  {entry.targetHeadline && (
                    <div className="max-w-[160px] truncate text-[11px] text-zinc-500">
                      {entry.targetHeadline}
                    </div>
                  )}
                </td>

                {/* Status */}
                <td className="px-4 py-3 whitespace-nowrap">
                  {getStatusBadge(entry.status)}
                </td>

                {/* Draft Excerpt */}
                <td className="max-w-xs truncate px-4 py-3 text-zinc-400">
                  {entry.error ? (
                    <span className="text-rose-400">Error: {entry.error}</span>
                  ) : (
                    entry.draftExcerpt
                  )}
                </td>

                {/* Inspect Action */}
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedEntry(entry);
                    }}
                    className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                  >
                    <ArrowSquareOut size={14} />
                  </button>
                </td>
              </tr>
            ))}

            {filteredEntries.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-xs text-zinc-500">
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-xl rounded-lg border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-zinc-100">
                    Audit Record Details
                  </h3>
                  {getStatusBadge(selectedEntry.status)}
                </div>
                <p className="mt-1 font-mono text-xs text-zinc-400">
                  Item ID: {selectedEntry.itemId}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="rounded-md border border-zinc-800 p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              >
                Close
              </button>
            </div>

            <div className="mt-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-zinc-800/80 pb-2">
                <span className="text-zinc-500">Action Type</span>
                <span className="text-zinc-200 uppercase">{selectedEntry.actionType}</span>
              </div>
              <div className="flex justify-between border-b border-zinc-800/80 pb-2">
                <span className="text-zinc-500">Decision Timestamp</span>
                <span className="text-zinc-200">{selectedEntry.decidedAt}</span>
              </div>
              {selectedEntry.executedAt && (
                <div className="flex justify-between border-b border-zinc-800/80 pb-2">
                  <span className="text-zinc-500">Execution Timestamp</span>
                  <span className="text-zinc-200">{selectedEntry.executedAt}</span>
                </div>
              )}
              {selectedEntry.targetAuthor && (
                <div className="flex justify-between border-b border-zinc-800/80 pb-2">
                  <span className="text-zinc-500">Target Author</span>
                  <span className="text-zinc-200">{selectedEntry.targetAuthor}</span>
                </div>
              )}
              {selectedEntry.targetUrl && (
                <div className="flex justify-between border-b border-zinc-800/80 pb-2">
                  <span className="text-zinc-500">Target Post URL</span>
                  <a
                    href={selectedEntry.targetUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="max-w-xs truncate text-emerald-400 hover:underline"
                  >
                    {selectedEntry.targetUrl}
                  </a>
                </div>
              )}
              {selectedEntry.error && (
                <div className="rounded-md border border-rose-500/20 bg-rose-500/10 p-2.5 text-rose-300">
                  <p className="font-semibold">Execution Failure:</p>
                  <p className="mt-1">{selectedEntry.error}</p>
                </div>
              )}
              {selectedEntry.draftExcerpt && (
                <div className="pt-2">
                  <span className="text-zinc-500">Draft Content:</span>
                  <div className="mt-1 rounded-md border border-zinc-800 bg-zinc-950 p-3 font-sans text-xs leading-relaxed text-zinc-300">
                    {selectedEntry.draftExcerpt}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
