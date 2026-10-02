import React from "react";
import { ChatTeardropDots, CheckCircle } from "../icons";

export interface HighImpactComment {
  id: string;
  author: string;
  headline: string;
  topic: string;
  commentExcerpt: string;
  authorReplied: boolean;
  reach: string;
  timestamp: string;
}

export interface HighImpactCommentsTableProps {
  comments: HighImpactComment[];
}

export const HighImpactCommentsTable: React.FC<HighImpactCommentsTableProps> = ({
  comments,
}) => {
  return (
    <div
      data-testid="high-impact-comments-table"
      className="rounded-lg border border-outline/70 bg-surface-container-lowest p-4 shadow-2xs flex flex-col gap-2.5"
    >
      <div className="flex flex-col justify-between gap-1 border-b border-outline/50 pb-2.5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-tertiary/10 text-tertiary">
            <ChatTeardropDots size={15} weight="bold" />
          </div>
          <h2 className="text-xs font-semibold text-on-surface">
            Recent High-Impact Comments
          </h2>
        </div>
        <span className="text-[11px] text-on-surface-variant">
          Top performing executed comments with author responses
        </span>
      </div>

      <div className="mt-0.5 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-outline/50 text-[11px] font-mono text-on-surface-variant">
              <th className="pb-2 font-medium">Target Author</th>
              <th className="pb-2 font-medium">Topic Tag</th>
              <th className="pb-2 font-medium">Comment Excerpt</th>
              <th className="pb-2 font-medium">Response Status</th>
              <th className="pb-2 font-medium">Reach</th>
              <th className="pb-2 font-medium text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline/40">
            {comments.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant text-[11px]">
                  No high-impact comments recorded yet. Comments will appear here once executed and engagement is tracked.
                </td>
              </tr>
            ) : (
              comments.map((comment) => {
                const initials = comment.author
                  .split(" ")
                  .map((p) => p[0])
                  .filter(Boolean)
                  .slice(0, 2)
                  .join("")
                  .toUpperCase() || "AU";

                return (
                  <tr
                    key={comment.id}
                    data-testid={`comment-row-${comment.id}`}
                    className="hover:bg-surface-container-low/60 transition-colors"
                  >
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded-md bg-surface-container-high text-on-surface-variant flex items-center justify-center text-[9px] font-bold border border-outline/60 shrink-0">
                          {initials}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs text-on-surface font-semibold truncate">
                            {comment.author}
                          </div>
                          <div className="text-[10px] text-on-surface-variant line-clamp-1">
                            {comment.headline}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3 whitespace-nowrap">
                      <span className="rounded-[4px] border border-outline/60 bg-surface-container-low px-1.5 py-0.2 font-mono text-[10px] text-on-surface">
                        {comment.topic}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 max-w-xs">
                      <p className="line-clamp-2 text-on-surface-variant leading-relaxed text-xs">
                        &quot;{comment.commentExcerpt}&quot;
                      </p>
                    </td>
                    <td className="py-2.5 pr-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 rounded-[4px] border border-tertiary/25 bg-tertiary/10 px-2 py-0.5 text-[10px] font-semibold text-tertiary">
                        <CheckCircle size={11} weight="bold" />
                        Author Replied
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-on-surface whitespace-nowrap font-medium tabular-nums">
                      {comment.reach}
                    </td>
                    <td className="py-2.5 font-mono text-[11px] text-on-surface-variant text-right whitespace-nowrap">
                      {comment.timestamp}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
