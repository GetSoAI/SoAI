"""SoAI - Browser Playwright error classification [backend/mcp/tools/browser/playwright_error_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = (
    "CHROME_INTERNAL_ERROR_URL",
    "is_browser_target_closed_error",
    "is_chrome_internal_error_url",
    "is_download_starting_error",
    "is_download_starting_message",
    "is_execution_context_destroyed_error",
    "is_interrupted_chrome_internal_navigation_error",
    "is_loopback_connection_refused_error",
    "is_navigation_timeout_error",
    "is_transient_snapshot_error",
    "is_usable_final_navigation_url",
    "resolve_chromium_net_error_code",
)

CHROME_INTERNAL_ERROR_URL = "chrome-error://chromewebdata/"

_CHROMIUM_NET_ERROR_CODE_PATTERN_TEXT = r"\bnet::(ERR_[A-Z0-9_]+)"
_NAVIGATION_TIMEOUT_PATTERN_TEXT = r"\btimeout \d+ms exceeded\b"
_URL_TOKEN_PATTERN_TEXT = r"\b[a-z][a-z0-9+.-]*:\S+"
_TARGET_CLOSED_WORD_PATTERN_TEXT = r"\b(?:closed|crashed)\b"

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


def is_chrome_internal_error_url(url: str) -> bool:
    return str(url or "").strip().lower() == CHROME_INTERNAL_ERROR_URL


def is_usable_final_navigation_url(final_url: str) -> bool:
    normalized_url = str(final_url or "").strip()
    if not normalized_url:
        return False
    return normalized_url.lower() != "about:blank" and not is_chrome_internal_error_url(
        normalized_url,
    )


def _first_error_message_line(exception: BaseException) -> str:
    return str(exception).partition("\n")[0]


def resolve_chromium_net_error_code(exception: BaseException) -> str | None:
    match = re.search(
        _CHROMIUM_NET_ERROR_CODE_PATTERN_TEXT,
        _first_error_message_line(exception),
    )
    return match.group(1) if match is not None else None


def is_navigation_timeout_error(exception: BaseException) -> bool:
    if isinstance(exception, TimeoutError):
        return True
    return (
        re.search(
            _NAVIGATION_TIMEOUT_PATTERN_TEXT,
            _first_error_message_line(exception),
            re.IGNORECASE,
        )
        is not None
    )


def is_browser_target_closed_error(exception: BaseException) -> bool:
    first_line = re.sub(
        _URL_TOKEN_PATTERN_TEXT,
        "",
        _first_error_message_line(exception),
        flags=re.IGNORECASE,
    )
    return re.search(_TARGET_CLOSED_WORD_PATTERN_TEXT, first_line, re.IGNORECASE) is not None


def is_transient_snapshot_error(exception: BaseException) -> bool:
    message = str(exception).strip().lower()
    if not message:
        return False
    return any(snippet in message for snippet in _TRANSIENT_SNAPSHOT_ERROR_SNIPPETS)
