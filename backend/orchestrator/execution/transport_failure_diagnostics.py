"""SoAI - Transport failure diagnostics sanitization helpers [backend/orchestrator/execution/transport_failure_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.security.public_text_redaction import (
    bound_public_text,
    redact_public_text_fragments,
)

__all__ = (
    "sanitize_health_ping_detail",
    "sanitize_transport_detail",
)


def sanitize_transport_detail(text: str) -> str:
    normalized = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if not normalized:
        return "unknown transport error"
    return bound_public_text(redact_public_text_fragments(normalized), max_length=200)


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
    return sanitize_transport_detail(first_line)
