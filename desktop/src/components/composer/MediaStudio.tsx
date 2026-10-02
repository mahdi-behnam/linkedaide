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
      className="p-5 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-surface-container-high/60">
        <div className="flex items-center gap-2">
          {activeMedia?.media_type === "carousel_pdf" ? (
            <FilePdf size={18} className="text-error" />
          ) : (
            <ImageIcon size={18} className="text-primary" />
          )}
          <span className="font-headline-sm text-headline-sm text-on-surface">
            Media Studio
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-label-sm text-label-sm px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-medium">
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
              className="p-1 rounded-lg text-on-surface-variant hover:text-error hover:bg-error-container/30 transition-colors"
            >
              <Trash size={15} />
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
          className="p-5 rounded-xl bg-surface-container-low border border-dashed border-outline-variant flex flex-col items-center justify-center text-center gap-2.5 hover:bg-surface-container transition-colors cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-full bg-surface-container-lowest flex items-center justify-center text-primary shadow-xs group-hover:scale-105 transition-transform border border-surface-container-high">
            <UploadSimple size={20} />
          </div>
          <div className="flex flex-col">
            <span className="font-body-strong text-body-strong text-on-surface">
              Drop carousel PDF or slides
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Multi-slide document (1080x1350 recommended)
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="px-2.5 py-1 rounded-lg bg-surface-container-lowest text-on-surface text-label-md font-label-md font-medium shadow-2xs hover:bg-surface-container-highest transition-colors flex items-center gap-1 border border-surface-container-high"
            >
              <FilePdf size={14} className="text-primary" />
              <span>PDF Carousel</span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="px-2.5 py-1 rounded-lg bg-surface-container-lowest text-on-surface text-label-md font-label-md font-medium shadow-2xs hover:bg-surface-container-highest transition-colors flex items-center gap-1 border border-surface-container-high"
            >
              <ImageIcon size={14} className="text-on-surface-variant" />
              <span>Single Image</span>
            </button>
          </div>
        </div>
      ) : (
        /* Active Media Canvas & Carousel Controls */
        <div className="flex flex-col gap-3">
          {/* File Name & Slide Count Strip */}
          <div className="flex items-center justify-between font-mono text-[11px] text-on-surface-variant px-1">
            <span className="truncate max-w-[200px]" title={activeMedia.file_name}>
              {activeMedia.file_name}
            </span>
            <span className="rounded bg-surface-container px-2 py-0.5 text-on-surface font-medium">
              {activeMedia.media_type === "carousel_pdf"
                ? `${activeMedia.slide_count} Slides`
                : "Single Image"}
            </span>
          </div>

          {/* Interactive Slide Canvas */}
          <div className="relative aspect-4/3 w-full overflow-hidden rounded-xl border border-surface-container-high bg-surface-container-low p-4 shadow-inner">
            {activeMedia.media_type === "carousel_pdf" ? (
              <div className="flex h-full flex-col justify-between">
                {/* Slide Top Bar */}
                <div className="flex items-center justify-between border-b border-surface-container-high/80 pb-2">
                  <span className="font-mono text-[10px] text-primary uppercase tracking-widest font-semibold">
                    LinkedIn High-Signal Carousel
                  </span>
                  <span className="font-mono text-[10px] text-on-surface-variant">
                    Slide {currentSlideIndex + 1} of {totalSlides}
                  </span>
                </div>

                {/* Slide Center Graphic */}
                <div className="flex flex-1 flex-col items-center justify-center p-3 text-center">
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-error-container/40 text-error border border-error/20">
                    <FilePdf size={24} />
                  </div>
                  <h3 className="text-xs font-semibold text-on-surface truncate max-w-xs">
                    {activeMedia.file_name}
                  </h3>
                  <p className="mt-1 font-mono text-[11px] text-on-surface-variant">
                    Slide {currentSlideIndex + 1}:{" "}
                    {CAROUSEL_SLIDE_LABELS[currentSlideIndex % CAROUSEL_SLIDE_LABELS.length]?.desc || "Page Preview"}
                  </p>
                  <span className="mt-1 text-[10px] text-on-surface-variant/70">
                    1080 x 1350 High-Res Document
                  </span>
                </div>

                {/* Slide Footer */}
                <div className="flex items-center justify-between border-t border-surface-container-high/80 pt-2 font-mono text-[10px] text-on-surface-variant">
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
                    className="max-h-40 max-w-full rounded object-contain"
                  />
                ) : (
                  <ImageIcon size={40} className="text-primary" />
                )}
                <p className="mt-2 text-xs font-medium text-on-surface truncate max-w-xs">
                  {activeMedia.file_name}
                </p>
                <p className="mt-1 text-[11px] text-on-surface-variant">
                  Single Image Attachment
                </p>
              </div>
            )}
          </div>

          {/* Multi-Slide Navigation Bar */}
          {activeMedia.media_type === "carousel_pdf" && (
            <div className="flex items-center justify-between rounded-xl border border-surface-container-high bg-surface-container-low px-3 py-2">
              <button
                type="button"
                data-testid="prev-slide-btn"
                disabled={currentSlideIndex === 0}
                onClick={() => setCurrentSlideIndex((prev) => Math.max(0, prev - 1))}
                className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <CaretLeft size={14} />
                <span>Previous</span>
              </button>

              <span
                data-testid="slide-indicator"
                className="font-mono text-xs font-semibold text-on-surface"
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
                className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <span>Next</span>
                <CaretRight size={14} />
              </button>
            </div>
          )}

          {/* Carousel 5-Slide Preview Strip (Matching Stitch lines 208-241) */}
          {activeMedia.media_type === "carousel_pdf" && (
            <div className="flex flex-col gap-1.5 mt-1">
              <div className="flex items-center justify-between text-on-surface-variant">
                <span className="font-label-sm text-label-sm font-medium">
                  Carousel Preview ({totalSlides} Slides)
                </span>
                <span className="font-code-sm text-code-sm text-tertiary font-semibold flex items-center gap-1">
                  <CheckCircle size={12} weight="bold" />
                  <span>PDF Ready</span>
                </span>
              </div>
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
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
                      className={`shrink-0 w-14 h-18 rounded-lg flex flex-col items-center justify-between p-1.5 transition-all text-left border ${
                        isCurrent
                          ? "bg-surface-container-highest border-primary ring-1 ring-primary shadow-xs"
                          : "bg-surface-container border-surface-container-high hover:border-surface-container-highest"
                      }`}
                    >
                      <span
                        className={`font-code-sm text-[10px] font-semibold truncate ${
                          isCurrent ? "text-primary" : "text-on-surface-variant"
                        }`}
                      >
                        {item.label}
                      </span>
                      <Article
                        size={18}
                        className={isCurrent ? "text-primary" : "text-on-surface-variant"}
                      />
                      <span
                        className={`w-full h-1 rounded-full ${
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
