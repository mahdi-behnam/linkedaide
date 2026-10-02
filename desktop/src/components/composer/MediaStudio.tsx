import React, { useRef } from "react";
import { MediaAttachment } from "../../types";
import {
  FilePdf,
  Image as ImageIcon,
  UploadSimple,
  Trash,
  CaretLeft,
  CaretRight,
  Article,
  CheckCircle,
} from "../icons";

interface MediaStudioProps {
  mediaList: MediaAttachment[];
  currentSlideIndex: number;
  setCurrentSlideIndex: React.Dispatch<React.SetStateAction<number>>;
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveMedia: () => void;
}

const CAROUSEL_SLIDE_LABELS = [
  { label: "#1 Cover", desc: "Hook & Title" },
  { label: "#2 Invariant", desc: "Core Problem" },
  { label: "#3 Arch", desc: "Architecture" },
  { label: "#4 Queue", desc: "Verification" },
  { label: "#5 Recap", desc: "Actionable Takeaways" },
];

export const MediaStudio: React.FC<MediaStudioProps> = ({
  mediaList,
  currentSlideIndex,
  setCurrentSlideIndex,
  onFileUpload,
  onRemoveMedia,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const activeMedia = mediaList[0];
  const totalSlides = activeMedia?.slide_count || 1;

  return (
    <div
      data-testid="media-previewer"
      className="p-4 rounded-lg bg-surface-container-lowest border border-outline/70 shadow-2xs flex flex-col gap-3.5"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-outline/50">
        <div className="flex items-center gap-2">
          {activeMedia?.media_type === "carousel_pdf" ? (
            <FilePdf size={16} className="text-error" />
          ) : (
            <ImageIcon size={16} className="text-primary" />
          )}
          <span className="text-xs font-semibold text-on-surface">
            Media Studio
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-on-surface-variant font-medium">
            {activeMedia
              ? activeMedia.media_type === "carousel_pdf"
                ? "Carousel PDF"
                : "Single Image"
              : "Visual Attachments"}
          </span>
          {activeMedia && (
            <button
              type="button"
              data-testid="remove-media-btn"
              onClick={onRemoveMedia}
              title="Remove media attachment"
              className="p-1 rounded-md text-on-surface-variant hover:text-error hover:bg-error-container/20 transition-colors"
            >
              <Trash size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        data-testid="media-file-input"
        type="file"
        accept="application/pdf,image/png,image/jpeg,image/webp"
        onChange={onFileUpload}
        className="hidden"
      />

      {/* Dropzone View (when no media attached) */}
      {!activeMedia ? (
        <div
          data-testid="media-dropzone"
          onClick={() => fileInputRef.current?.click()}
          className="p-4 rounded-md bg-surface-container-low border border-dashed border-outline flex flex-col items-center justify-center text-center gap-2 hover:bg-surface-container transition-colors cursor-pointer group"
        >
          <div className="w-8 h-8 rounded-md bg-surface-container-lowest flex items-center justify-center text-primary shadow-2xs border border-outline/60">
            <UploadSimple size={16} />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-on-surface">
              Drop carousel PDF or slides
            </span>
            <span className="text-[11px] text-on-surface-variant">
              Multi-slide document (1080x1350 recommended)
            </span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="px-2.5 py-1 rounded-md bg-surface-container-lowest text-on-surface text-xs font-medium shadow-2xs hover:bg-surface-container-high transition-colors flex items-center gap-1 border border-outline/60"
            >
              <FilePdf size={13} className="text-primary" />
              <span>PDF Carousel</span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="px-2.5 py-1 rounded-md bg-surface-container-lowest text-on-surface text-xs font-medium shadow-2xs hover:bg-surface-container-high transition-colors flex items-center gap-1 border border-outline/60"
            >
              <ImageIcon size={13} className="text-on-surface-variant" />
              <span>Single Image</span>
            </button>
          </div>
        </div>
      ) : (
        /* Active Media Canvas & Carousel Controls */
        <div className="flex flex-col gap-2.5">
          {/* File Name & Slide Count Strip */}
          <div className="flex items-center justify-between font-mono text-[11px] text-on-surface-variant px-0.5">
            <span className="truncate max-w-[200px]" title={activeMedia.file_name}>
              {activeMedia.file_name}
            </span>
            <span className="text-on-surface font-medium text-[11px]">
              {activeMedia.media_type === "carousel_pdf"
                ? `${activeMedia.slide_count} Slides`
                : "Single Image"}
            </span>
          </div>

          {/* Interactive Slide Canvas */}
          <div className="relative aspect-4/3 w-full overflow-hidden rounded-md border border-outline/60 bg-surface-container-low p-3.5 shadow-2xs">
            {activeMedia.media_type === "carousel_pdf" ? (
              <div className="flex h-full flex-col justify-between">
                {/* Slide Top Bar */}
                <div className="flex items-center justify-between border-b border-outline/50 pb-1.5">
                  <span className="font-mono text-[10px] text-primary uppercase tracking-wider font-semibold">
                    LinkedIn Carousel Preview
                  </span>
                  <span className="font-mono text-[10px] text-on-surface-variant tabular-nums">
                    Slide {currentSlideIndex + 1} of {totalSlides}
                  </span>
                </div>

                {/* Slide Center Graphic */}
                <div className="flex flex-1 flex-col items-center justify-center p-2 text-center">
                  <div className="mb-1.5 flex h-10 w-10 items-center justify-center rounded-md bg-error-container/30 text-error border border-error/20">
                    <FilePdf size={20} />
                  </div>
                  <h3 className="text-xs font-semibold text-on-surface truncate max-w-xs">
                    {activeMedia.file_name}
                  </h3>
                  <p className="mt-0.5 font-mono text-[11px] text-on-surface-variant">
                    Slide {currentSlideIndex + 1}:{" "}
                    {CAROUSEL_SLIDE_LABELS[currentSlideIndex % CAROUSEL_SLIDE_LABELS.length]?.desc || "Page Preview"}
                  </p>
                  <span className="mt-0.5 text-[10px] text-on-surface-variant/70">
                    1080 x 1350 Document
                  </span>
                </div>

                {/* Slide Footer */}
                <div className="flex items-center justify-between border-t border-outline/50 pt-1.5 font-mono text-[10px] text-on-surface-variant">
                  <span>Swipe to explore &rarr;</span>
                  <span className="text-primary font-medium">PDF Carousel</span>
                </div>
              </div>
            ) : (
              /* Image Canvas */
              <div className="flex h-full flex-col items-center justify-center text-center p-2">
                {activeMedia.file_url &&
                (activeMedia.file_url.startsWith("blob:") ||
                  activeMedia.file_url.startsWith("data:") ||
                  activeMedia.file_url.startsWith("http")) ? (
                  <img
                    src={activeMedia.file_url}
                    alt={activeMedia.file_name}
                    className="max-h-36 max-w-full rounded object-contain"
                  />
                ) : (
                  <ImageIcon size={36} className="text-primary" />
                )}
                <p className="mt-1.5 text-xs font-medium text-on-surface truncate max-w-xs">
                  {activeMedia.file_name}
                </p>
                <p className="mt-0.5 text-[11px] text-on-surface-variant">
                  Single Image Attachment
                </p>
              </div>
            )}
          </div>

          {/* Multi-Slide Navigation Bar */}
          {activeMedia.media_type === "carousel_pdf" && (
            <div className="flex items-center justify-between rounded-md border border-outline/60 bg-surface-container-low px-2.5 py-1.5">
              <button
                type="button"
                data-testid="prev-slide-btn"
                disabled={currentSlideIndex === 0}
                onClick={() => setCurrentSlideIndex((prev) => Math.max(0, prev - 1))}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <CaretLeft size={13} />
                <span>Previous</span>
              </button>

              <span
                data-testid="slide-indicator"
                className="font-mono text-xs font-medium text-on-surface tabular-nums"
              >
                Slide {currentSlideIndex + 1} of {totalSlides}
              </span>

              <button
                type="button"
                data-testid="next-slide-btn"
                disabled={currentSlideIndex >= totalSlides - 1}
                onClick={() =>
                  setCurrentSlideIndex((prev) =>
                    Math.min(totalSlides - 1, prev + 1)
                  )
                }
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <span>Next</span>
                <CaretRight size={13} />
              </button>
            </div>
          )}

          {/* Carousel 5-Slide Preview Strip */}
          {activeMedia.media_type === "carousel_pdf" && (
            <div className="flex flex-col gap-1.5 mt-1">
              <div className="flex items-center justify-between text-on-surface-variant">
                <span className="text-[11px] font-medium text-on-surface">
                  Carousel Preview ({totalSlides} Slides)
                </span>
                <span className="text-[10px] text-tertiary font-medium flex items-center gap-1">
                  <CheckCircle size={12} weight="bold" />
                  <span>PDF Ready</span>
                </span>
              </div>
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
                {Array.from({ length: totalSlides }).map((_, idx) => {
                  const isCurrent = idx === currentSlideIndex;
                  const item = CAROUSEL_SLIDE_LABELS[idx] || {
                    label: `#${idx + 1}`,
                    desc: "Slide",
                  };

                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setCurrentSlideIndex(idx)}
                      className={`shrink-0 w-13 h-16 rounded-md flex flex-col items-center justify-between p-1.5 transition-colors text-left border ${
                        isCurrent
                          ? "bg-surface-bright border-primary/60 shadow-2xs"
                          : "bg-surface-container border-outline/50 hover:border-outline"
                      }`}
                    >
                      <span
                        className={`font-mono text-[9px] font-semibold truncate ${
                          isCurrent ? "text-primary" : "text-on-surface-variant"
                        }`}
                      >
                        {item.label}
                      </span>
                      <Article
                        size={16}
                        className={isCurrent ? "text-primary" : "text-on-surface-variant"}
                      />
                      <span
                        className={`w-full h-0.5 rounded-xs ${
                          isCurrent ? "bg-primary" : "bg-outline-variant"
                        }`}
                      />
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
