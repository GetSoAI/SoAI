"""SoAI - Transport failure diagnostics sanitization helpers [backend/orchestrator/execution/transport_failure_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = (
    "sanitize_health_ping_detail",
    "sanitize_transport_detail",
)

_URL_PATTERN_TEXT = r"https?://\S+"
_HOSTPORT_PATTERN_TEXT = r"\b(?:(?:\d{1,3}\.){3}\d{1,3}|localhost)(?::\d{1,5})\b"
_UNIX_FS_PATH_PATTERN_TEXT = r"\b/(?:opt|home|var|tmp|usr|etc|root|mnt)(?:/[A-Za-z0-9._-]+)+\b"
_WIN_FS_PATH_PATTERN_TEXT = r"\b[A-Za-z]:\\[^\s]+"


def sanitize_transport_detail(text: str) -> str:
    normalized = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if not normalized:
        return "unknown transport error"
    normalized = re.sub(_URL_PATTERN_TEXT, "<redacted_url>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        _HOSTPORT_PATTERN_TEXT,
        "<redacted_endpoint>",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        _UNIX_FS_PATH_PATTERN_TEXT,
        "<redacted_path>",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        _WIN_FS_PATH_PATTERN_TEXT,
        "<redacted_path>",
        normalized,
        flags=re.IGNORECASE,
    )
    if len(normalized) > 200:
        return f"{normalized[:197]}..."
    return normalized


def sanitize_health_ping_detail(text: str) -> str:
    first_line = str(text or "").splitlines()[0].strip()
    if not first_line:
        return "unknown"
    log_index = first_line.find(" Log:")
    if log_index != -1:
        first_line = first_line[:log_index].strip()
    recent_log_index = first_line.find(" Recent log:")
    if recent_log_index != -1:
        first_line = first_line[:recent_log_index].strip()
    if not first_line:
        return "unknown"
    sanitized = sanitize_transport_detail(first_line)
    if len(sanitized) > 200:
        return f"{sanitized[:197]}..."
    return sanitized
