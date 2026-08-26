"""SoAI - Agent turn timing validation [backend/core/agent/turn_timing_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("has_valid_execution_timing",)


def has_valid_execution_timing(
    *,
    status: str,
    running_status: str,
    terminal_statuses: tuple[str, ...],
    started_at_ms: int,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> bool:
    if updated_at_ms < started_at_ms:
        return False
    if finished_at_ms is not None and finished_at_ms < updated_at_ms:
        return False
    if status == running_status and finished_at_ms is not None:
        return False
    if status in terminal_statuses and finished_at_ms is None:
        return False
    return True
