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
          <span className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
            <CheckCircle size={10} weight="bold" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-semibold">
            <Clock size={10} weight="bold" />
            <span>Scheduled</span>
          </span>
        );
      case "draft":
      default:
        return (
          <span className="inline-flex items-center gap-1 font-label-sm text-[10px] px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-medium">
            <PencilSimple size={10} />
            <span>Draft</span>
          </span>
        );
    }
  };

  return (
    <div
      data-testid="post-detail-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-xl rounded-2xl border border-surface-container-high bg-surface-container-lowest p-6 shadow-2xl flex flex-col gap-4">
        {/* Modal Header */}
        <div className="flex items-start justify-between pb-3 border-b border-surface-container-high/70">
          <div>
            <div className="flex items-center gap-2">
              {getStatusBadge(post.status)}
              <span className="rounded-full bg-surface-container px-2 py-0.5 font-mono text-[10px] text-on-surface-variant font-medium">
                {post.topic_pillar}
              </span>
            </div>
            <h3 className="mt-2 text-base font-semibold text-on-surface">
              {post.headline || "Original Scheduled Post"}
            </h3>
          </div>
          <button
            type="button"
            data-testid="close-modal-btn"
            onClick={onClose}
            className="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Post Content Excerpt */}
        <div className="max-h-60 overflow-y-auto rounded-xl border border-surface-container-high bg-surface-container-low p-4 font-sans text-xs leading-relaxed text-on-surface whitespace-pre-wrap">
          {post.post_text}
        </div>

        {/* Media Information */}
        {post.media.length > 0 && (
          <div className="rounded-xl border border-surface-container-high bg-surface-container-low p-3.5 flex flex-col gap-2">
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
                    <FilePdf size={16} className="text-error" />
                  ) : (
                    <ImageIcon size={16} className="text-primary" />
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
        <div className="flex items-center justify-between pt-3 border-t border-surface-container-high/70">
          <span className="font-mono text-[11px] text-on-surface-variant">
            Scheduled:{" "}
            {post.scheduled_time
              ? new Date(post.scheduled_time).toUTCString()
              : "Draft"}
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-surface-container-high bg-surface-container-low px-3.5 py-1.5 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors font-medium"
            >
              Close
            </button>
            <button
              type="button"
              data-testid="edit-in-composer-btn"
              onClick={() => onEditInComposer(post)}
              className="flex items-center gap-1.5 rounded-xl bg-primary hover:bg-primary-container px-3.5 py-1.5 text-xs font-semibold text-on-primary transition-colors shadow-2xs"
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
