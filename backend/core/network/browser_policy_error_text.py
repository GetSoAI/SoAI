"""SoAI - Browser policy error text normalization [backend/core/network/browser_policy_error_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "is_browser_policy_error_message",
    "normalize_browser_policy_error_message",
)

_WRAPPER_PREFIXES: tuple[str, ...] = (
    "Browser.new_context:",
    "BrowserContext.new_page:",
    "Page.goto:",
    "Page.set_content:",
    "Route.continue_:",
)
_POLICY_MESSAGE_MARKERS: tuple[str, ...] = (
    "Disallowed hostname for ",
    "Disallowed IP address for ",
    "Disallowed resolved IP address for ",
    "DNS resolution produced no results for host:",
    "DNS resolution produced no IP addresses for host:",
)


def normalize_browser_policy_error_message(message: str) -> str:
    normalized_message = str(message or "").strip()
    if not normalized_message:
        return normalized_message
    changed = True
    while changed:
        changed = False
        for prefix in _WRAPPER_PREFIXES:
            if normalized_message.startswith(prefix):
                normalized_message = normalized_message[len(prefix) :].strip()
                changed = True
    return normalized_message


def is_browser_policy_error_message(message: str) -> bool:
    normalized_message = normalize_browser_policy_error_message(message)
    return any(marker in normalized_message for marker in _POLICY_MESSAGE_MARKERS)
