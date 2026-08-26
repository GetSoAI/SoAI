"""SoAI - Stable notification admin alert identity helpers [backend/core/notifications/admin_alert_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

__all__ = (
    "build_admin_alert_id",
    "normalize_admin_alert_label",
)

MAX_LABEL_LENGTH = 120


def normalize_admin_alert_label(value: str, fallback: str) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        normalized = fallback.strip()
    if len(normalized) <= MAX_LABEL_LENGTH:
        return normalized
    return f"{normalized[: MAX_LABEL_LENGTH - 3].rstrip()}..."


def build_admin_alert_id(prefix: str, parts: tuple[str, ...]) -> str:
    normalized_prefix = str(prefix or "").strip()
    if not normalized_prefix:
        normalized_prefix = "admin_alert"
    digest_input = "\u001f".join(str(part or "").strip() for part in parts)
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:32]
    return f"{normalized_prefix}:{digest}"
