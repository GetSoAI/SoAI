"""SoAI - HTTP header validation helpers [backend/core/validation/http_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("content_type_is_json",)


def content_type_is_json(content_type: str | None) -> bool:
    if not isinstance(content_type, str):
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        return True
    if media_type.startswith("application/") and media_type.endswith("+json"):
        return True
    return False
