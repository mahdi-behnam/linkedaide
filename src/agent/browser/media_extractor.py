"""Multimodal media extractor for LinkedIn post cards."""

from __future__ import annotations

from typing import Any

CAROUSEL_SELECTORS: list[str] = [
    ".feed-shared-carousel",
    ".artdeco-carousel",
    ".artdeco-carousel__item",
    ".artdeco-carousel__slide",
    "div[data-carousel-item]",
    ".feed-shared-document-preview",
    ".feed-shared-document",
    "iframe.feed-shared-document__iframe",
    ".update-components-document",
    "div.document-container",
]

IMAGE_SELECTORS: list[str] = [
    ".update-components-image__image",
    ".feed-shared-image img",
    "div[data-view-name='feed-full-update'] img.feed-shared-image__image",
    "img.feed-shared-image__image",
    "div.feed-shared-image img",
    "div.update-components-image img",
    "div.feed-shared-article__image img",
    ".feed-shared-document-preview img",
    "div.feed-shared-document-preview img",
    "img.ivm-view-attr__img--centered",
]

VIDEO_SELECTORS: list[str] = [
    ".feed-shared-linkedin-video",
    "video",
    ".update-components-linkedin-video",
]


async def extract_media_from_card(card: Any) -> tuple[str | None, str | None]:
    """Extract high-resolution media URL and detected media type from a post card locator.

    Detects:
    - Image elements (.update-components-image__image, .feed-shared-image img, etc.)
    - Carousel and document slide elements (.feed-shared-carousel, .artdeco-carousel, etc.)
    - Video elements (.feed-shared-linkedin-video, video)

    Returns:
        tuple[str | None, str | None]: (image_url, media_type)
    """
    detected_media_type: str | None = None
    extracted_image_url: str | None = None

    # 1. Detect document/carousel slide elements
    for c_sel in CAROUSEL_SELECTORS:
        try:
            c_loc = card.locator(c_sel)
            if await c_loc.count() > 0:
                if "document" in c_sel:
                    detected_media_type = "document"
                else:
                    detected_media_type = "carousel"
                break
        except Exception:
            continue

    # 2. Check for video if not carousel
    if not detected_media_type:
        for v_sel in VIDEO_SELECTORS:
            try:
                v_loc = card.locator(v_sel)
                if await v_loc.count() > 0:
                    detected_media_type = "video"
                    try:
                        poster = await v_loc.first.get_attribute("poster")
                        if poster and poster.strip().startswith("http"):
                            extracted_image_url = poster.strip()
                    except Exception:
                        pass
                    break
            except Exception:
                continue

    # 3. Extract high-resolution image URL
    for i_sel in IMAGE_SELECTORS:
        try:
            i_loc = card.locator(i_sel).first
            if await i_loc.count() > 0:
                src = await i_loc.get_attribute("src")
                delayed_url = await i_loc.get_attribute("data-delayed-url")
                data_src = await i_loc.get_attribute("data-src")

                candidate_url: str | None = None
                for u in (delayed_url, src, data_src):
                    if u and u.strip().startswith("http"):
                        candidate_url = u.strip()
                        break

                if candidate_url:
                    extracted_image_url = candidate_url
                    if not detected_media_type:
                        detected_media_type = "image"
                    break
        except Exception:
            continue

    # 4. If carousel or document was detected but no image yet, check slide img
    if detected_media_type in ("carousel", "document") and not extracted_image_url:
        try:
            slide_img = card.locator(
                ".feed-shared-carousel img, .artdeco-carousel img, "
                ".feed-shared-document-preview img, div[data-carousel-item] img"
            ).first
            if await slide_img.count() > 0:
                src = await slide_img.get_attribute("src")
                delayed = await slide_img.get_attribute("data-delayed-url")
                for u in (delayed, src):
                    if u and u.strip().startswith("http"):
                        extracted_image_url = u.strip()
                        break
        except Exception:
            pass

    return extracted_image_url, detected_media_type
