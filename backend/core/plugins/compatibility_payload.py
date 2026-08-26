"""SoAI - Plugin compatibility payload formatting [backend/core/plugins/compatibility_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.compatibility import CompatibilityInfo
from core.types.json import JSONDict

__all__ = ("compatibility_to_payload",)


def compatibility_to_payload(info: CompatibilityInfo) -> JSONDict | None:
    if info.reason:
        return {
            "reason": info.reason.value,
            "can_override": info.can_override,
            "is_overridden": info.is_overridden,
            "details": info.details,
            "message": info.message,
        }
    return None
