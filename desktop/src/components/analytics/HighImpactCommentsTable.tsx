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
      className="rounded-xl border border-outline bg-surface-container-lowest p-5 shadow-2xs flex flex-col gap-3"
    >
      <div className="flex flex-col justify-between gap-1 border-b border-outline pb-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-tertiary/10 text-tertiary">
            <ChatTeardropDots size={16} weight="bold" />
          </div>
          <h2 className="headline-sm text-on-surface">
            Recent High-Impact Comments
          </h2>
        </div>
        <span className="code-sm text-on-surface-variant">
          Top performing executed comments with author responses
        </span>
      </div>

      <div className="mt-1 overflow-x-auto">
        <table className="w-full text-left body-md">
          <thead>
            <tr className="border-b border-outline text-[11px] font-mono text-on-surface-variant">
              <th className="pb-2.5 font-medium">Target Author</th>
              <th className="pb-2.5 font-medium">Topic Tag</th>
              <th className="pb-2.5 font-medium">Comment Excerpt</th>
              <th className="pb-2.5 font-medium">Response Status</th>
              <th className="pb-2.5 font-medium">Reach</th>
              <th className="pb-2.5 font-medium text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline/50">
            {comments.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">
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
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-6 h-6 rounded-full bg-surface-container-high text-on-surface-variant flex items-center justify-center text-[10px] font-bold border border-outline shrink-0">
                          {initials}
                        </div>
                        <div className="min-w-0">
                          <div className="body-strong text-on-surface font-semibold truncate">
                            {comment.author}
                          </div>
                          <div className="label-sm text-on-surface-variant line-clamp-1">
                            {comment.headline}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-3 whitespace-nowrap">
                      <span className="rounded-md border border-outline bg-surface-container-low px-2 py-0.5 code-sm text-on-surface">
                        {comment.topic}
                      </span>
                    </td>
                    <td className="py-3 pr-3 max-w-xs">
                      <p className="line-clamp-2 text-on-surface-variant leading-relaxed italic body-md">
                        "{comment.commentExcerpt}"
                      </p>
                    </td>
                    <td className="py-3 pr-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-tertiary/25 bg-tertiary/10 px-2.5 py-0.5 code-sm font-semibold text-tertiary">
                        <CheckCircle size={13} weight="bold" />
                        Author Replied
                      </span>
                    </td>
                    <td className="py-3 pr-3 code-sm text-on-surface whitespace-nowrap font-medium">
                      {comment.reach}
                    </td>
                    <td className="py-3 code-sm text-on-surface-variant text-right whitespace-nowrap">
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
