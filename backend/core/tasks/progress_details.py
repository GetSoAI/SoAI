"""SoAI - Task progress details serialization helper [backend/core/tasks/progress_details.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("serialize_progress_details",)


def serialize_progress_details(details: JSONValue | None) -> str:
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    return serialize_json_compact_stable(details)
