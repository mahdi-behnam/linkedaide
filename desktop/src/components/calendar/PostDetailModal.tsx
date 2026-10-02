import React from "react";
import { ScheduledPost, ScheduledPostStatus } from "../../types";
import {
  FilePdf,
  Image as ImageIcon,
  PencilSimple,
  X,
  Clock,
  CheckCircle,
} from "../icons";

interface PostDetailModalProps {
  post: ScheduledPost;
  onClose: () => void;
  onEditInComposer: (post: ScheduledPost) => void;
}

export const PostDetailModal: React.FC<PostDetailModalProps> = ({
  post,
  onClose,
  onEditInComposer,
}) => {
  const getStatusBadge = (status: ScheduledPostStatus) => {
    switch (status) {
      case "published":
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-tertiary font-medium">
            <CheckCircle size={13} weight="bold" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-primary font-medium">
            <Clock size={13} weight="bold" />
            <span>Scheduled</span>
          </span>
        );
      case "draft":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-on-surface-variant font-medium">
            <PencilSimple size={13} />
            <span>Draft</span>
          </span>
        );
    }
  };

  return (
    <div
      data-testid="post-detail-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-xl rounded-xl border border-outline/70 bg-surface-bright p-5 shadow-2xl flex flex-col gap-3.5">
        {/* Modal Header */}
        <div className="flex items-start justify-between pb-2.5 border-b border-outline/50">
          <div>
            <div className="flex items-center gap-2">
              {getStatusBadge(post.status)}
              <span className="font-mono text-[11px] text-on-surface-variant font-medium">
                · {post.topic_pillar}
              </span>
            </div>
            <h3 className="mt-2 text-sm font-semibold text-on-surface">
              {post.headline || "Original Scheduled Post"}
            </h3>
          </div>
          <button
            type="button"
            data-testid="close-modal-btn"
            onClick={onClose}
            className="rounded-md p-1 text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Post Content Excerpt */}
        <div className="max-h-60 overflow-y-auto rounded-md border border-outline/50 bg-surface-container-low p-3.5 font-sans text-xs leading-relaxed text-on-surface whitespace-pre-wrap">
          {post.post_text}
        </div>

        {/* Media Information */}
        {post.media.length > 0 && (
          <div className="rounded-md border border-outline/50 bg-surface-container-low p-3 flex flex-col gap-2">
            <div className="text-[11px] font-semibold text-on-surface-variant">
              Attached Media:
            </div>
            {post.media.map((m, i) => (
              <div
                key={i}
                className="flex items-center justify-between font-mono text-xs text-on-surface"
              >
                <div className="flex items-center gap-2">
                  {m.media_type === "carousel_pdf" ? (
                    <FilePdf size={15} className="text-error" />
                  ) : (
                    <ImageIcon size={15} className="text-primary" />
                  )}
                  <span className="font-medium">{m.file_name}</span>
                </div>
                <span className="text-[11px] text-on-surface-variant">
                  {m.media_type === "carousel_pdf"
                    ? `${m.slide_count} slides`
                    : "Single Image"}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-between pt-2.5 border-t border-outline/50">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Scheduled:{" "}
            {post.scheduled_time
              ? new Date(post.scheduled_time).toUTCString()
              : "Draft"}
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-outline/60 bg-surface-container-low px-3 py-1.5 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors font-medium"
            >
              Close
            </button>
            <button
              type="button"
              data-testid="edit-in-composer-btn"
              onClick={() => onEditInComposer(post)}
              className="flex items-center gap-1.5 rounded-md bg-primary hover:bg-primary/90 px-3 py-1.5 text-xs font-semibold text-on-primary transition-colors shadow-2xs"
            >
              <PencilSimple size={13} weight="bold" />
              <span>Edit in Composer</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
