"""SoAI - Browser Playwright error classification [backend/mcp/tools/browser/playwright_error_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "CHROME_INTERNAL_ERROR_URL",
    "is_download_starting_error",
    "is_download_starting_message",
    "is_execution_context_destroyed_error",
    "is_interrupted_chrome_internal_navigation_error",
    "is_loopback_connection_refused_error",
    "is_transient_snapshot_error",
    "is_usable_final_navigation_url",
)

CHROME_INTERNAL_ERROR_URL = "chrome-error://chromewebdata/"

_TRANSIENT_SNAPSHOT_ERROR_SNIPPETS: tuple[str, ...] = (
    "frame was detached",
    "execution context was destroyed",
    "target closed",
)


def is_download_starting_message(message: str) -> bool:
    return "download is starting" in message.lower()


def is_download_starting_error(exception: BaseException) -> bool:
    return is_download_starting_message(str(exception))


def is_execution_context_destroyed_error(exception: BaseException) -> bool:
    message = str(exception)
    return bool(message) and "Execution context was destroyed" in message


def is_loopback_connection_refused_error(exception: BaseException) -> bool:
    return "err_connection_refused" in str(exception).lower()


def is_interrupted_chrome_internal_navigation_error(exception: BaseException) -> bool:
    message = str(exception).lower()
    return "interrupted" in message and CHROME_INTERNAL_ERROR_URL in message


def is_usable_final_navigation_url(final_url: str) -> bool:
    normalized_url = str(final_url or "").strip()
    if not normalized_url:
        return False
    lowered_url = normalized_url.lower()
    return lowered_url not in ("about:blank", CHROME_INTERNAL_ERROR_URL)


def is_transient_snapshot_error(exception: BaseException) -> bool:
    message = str(exception).strip().lower()
    if not message:
        return False
    return any(snippet in message for snippet in _TRANSIENT_SNAPSHOT_ERROR_SNIPPETS)
