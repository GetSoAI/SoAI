"""SoAI - Browser navigation screenshot capture [backend/mcp/tools/browser/navigation_capture.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.inline_image_payload import (
    MAX_INLINE_IMAGE_BASE64_CHARS,
    build_inline_image_payload,
)
from core.files.inline_image_preparation import prepare_inline_image_for_prompt_relay
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict

__all__ = ("capture_navigation_screenshot",)

LOGGER_NAME = "SoAI.mcp.tools.navigation_capture"


def _build_navigation_screenshot_payload(
    *,
    image_bytes: bytes,
    content_type: str,
) -> tuple[JSONDict | None, str | None]:
    payload, failure_reason = build_inline_image_payload(
        content_type=content_type,
        image_bytes=image_bytes,
        max_base64_chars=MAX_INLINE_IMAGE_BASE64_CHARS,
    )
    if payload is not None:
        return (payload, None)
    prepared, prepare_failure_reason = prepare_inline_image_for_prompt_relay(
        image_bytes=image_bytes,
        declared_content_type=content_type,
        max_encoded_chars=MAX_INLINE_IMAGE_BASE64_CHARS,
    )
    if prepared is not None:
        return (prepared.payload, None)
    return (None, prepare_failure_reason or failure_reason)


async def capture_navigation_screenshot(
    *,
    page: Page,
    timeout_ms: int,
    operation: str,
    failure_message: str,
) -> tuple[JSONDict | None, str | None]:
    logger = get_logger(LOGGER_NAME)
    try:
        image_bytes_png = await page.screenshot(
            full_page=False,
            type="png",
            timeout=timeout_ms,
        )
        payload, oversized = _build_navigation_screenshot_payload(
            image_bytes=image_bytes_png,
            content_type="image/png",
        )
        if payload is not None:
            return (payload, None)
        if isinstance(oversized, str) and oversized.strip():
            return (None, oversized)
        return (None, "Screenshot exceeded the inline size limit after compression.")
    except (Error, TimeoutError) as exception:
        error = coerce_to_soai_error(
            exception,
            operation=operation,
        )
        log_exception(
            logger,
            error,
            message=failure_message,
            operation=operation,
            level="warning",
        )
        return (None, error.message)
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(
            exception,
            operation=operation,
        )
        log_exception(
            logger,
            error,
            message=failure_message,
            operation=operation,
            level="warning",
        )
        return (None, error.message)
