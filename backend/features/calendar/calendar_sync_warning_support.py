"""SoAI - Calendar sync warning support [backend/features/calendar/calendar_sync_warning_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = (
    "append_sync_warning",
    "extend_sync_warnings",
)


def append_sync_warning(sync_result: JSONDict, warning: str) -> None:
    warnings_value = sync_result.get("warnings")
    warnings = warnings_value if isinstance(warnings_value, list) else []
    warnings.append(warning)
    sync_result["warnings"] = warnings


def extend_sync_warnings(warnings: list[str], sync_result: JSONDict) -> None:
    warnings_value = sync_result.get("warnings")
    if not isinstance(warnings_value, list):
        return
    for warning in warnings_value:
        if isinstance(warning, str) and warning:
            warnings.append(warning)
