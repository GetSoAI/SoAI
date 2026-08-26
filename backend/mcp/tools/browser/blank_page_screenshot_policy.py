"""SoAI - Blank-page screenshot suppression policy [backend/mcp/tools/browser/blank_page_screenshot_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, UnidentifiedImageError
from playwright.async_api import Error

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.logging.protocols import LoggerProtocol

__all__ = (
    "is_solid_color_png",
    "should_skip_blank_screenshot",
)

_MIN_MEANINGFUL_TEXT_CHARS: int = 24


async def should_skip_blank_screenshot(
    *,
    page: Page,
    logger: LoggerProtocol,
    operation: str,
    url: str,
) -> bool:
    try:
        probe_result = await page.evaluate("""
(() => {
  const body = document.body;
  const root = document.documentElement;
  if (!body || !root) {
    return { text_len: 0, has_img: false, has_svg: false, has_canvas: false };
  }
  const textLen = ((body.innerText || '').trim()).length;
  const images = Array.from(document.images || []);
  const hasImg = images.some(img => (img.naturalWidth || 0) > 8 && (img.naturalHeight || 0) > 8);
  const hasSvg = body.querySelector('svg') !== null;
  const hasCanvas = body.querySelector('canvas') !== null;
  return { text_len: textLen, has_img: hasImg, has_svg: hasSvg, has_canvas: hasCanvas };
})()
""".strip())
    except (Error, TimeoutError) as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            error,
            message="Failed to probe page visual content during screenshot capture (non-critical).",
            operation=operation,
            details={"url": url},
            level="debug",
        )
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            error,
            message="Failed to probe page visual content during screenshot capture (non-critical).",
            operation=operation,
            details={"url": url},
            level="debug",
        )
        return False

    probe_payload = coerce_json_dict(probe_result)
    if probe_payload is None:
        return False
    text_len_value = probe_payload.get("text_len")
    has_img_value = probe_payload.get("has_img")
    has_svg_value = probe_payload.get("has_svg")
    has_canvas_value = probe_payload.get("has_canvas")
    text_len = int(text_len_value) if isinstance(text_len_value, int) else 0
    has_img = bool(has_img_value) if isinstance(has_img_value, bool) else False
    has_svg = bool(has_svg_value) if isinstance(has_svg_value, bool) else False
    has_canvas = bool(has_canvas_value) if isinstance(has_canvas_value, bool) else False
    has_meaningful_content = (
        text_len >= _MIN_MEANINGFUL_TEXT_CHARS or has_img or has_svg or has_canvas
    )
    return not has_meaningful_content


def is_solid_color_png(
    *,
    image_bytes_png: bytes,
    logger: LoggerProtocol,
    operation: str,
    url: str,
) -> bool:
    if not image_bytes_png:
        return True
    try:
        with Image.open(BytesIO(image_bytes_png)) as image:
            converted = image.convert("RGBA")
            extrema = converted.getextrema()
    except (UnidentifiedImageError, OSError, ValueError) as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            error,
            message="Failed to decode screenshot image during blank-screenshot check (non-critical).",
            operation=operation,
            details={"url": url},
            level="debug",
        )
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            error,
            message="Failed to analyze screenshot image during blank-screenshot check (non-critical).",
            operation=operation,
            details={"url": url},
            level="debug",
        )
        return False

    if (
        not isinstance(extrema, tuple)
        or len(extrema) != 4
        or not all(isinstance(item, tuple) and len(item) == 2 for item in extrema)
    ):
        return False
    red_extrema, green_extrema, blue_extrema, alpha_extrema = extrema
    if not (
        isinstance(red_extrema[0], int)
        and isinstance(red_extrema[1], int)
        and isinstance(green_extrema[0], int)
        and isinstance(green_extrema[1], int)
        and isinstance(blue_extrema[0], int)
        and isinstance(blue_extrema[1], int)
        and isinstance(alpha_extrema[0], int)
        and isinstance(alpha_extrema[1], int)
    ):
        return False

    if (
        red_extrema[0] == red_extrema[1]
        and green_extrema[0] == green_extrema[1]
        and blue_extrema[0] == blue_extrema[1]
        and alpha_extrema[0] == alpha_extrema[1]
    ):
        return True
    return False
