"""SoAI - Automation run and message identifier builders [backend/core/automation/automation_identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import build_soai_id

__all__ = (
    "build_automation_run_cancellation_id",
    "build_automation_run_trace_id",
    "build_automation_turn_request_id",
)


def build_automation_run_trace_id(run_id: str) -> str:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValidationError("Automation run trace id requires a non-empty run_id.")
    return build_soai_id(("req", "automation", "run", normalized_run_id))


def build_automation_run_cancellation_id(run_id: str) -> str:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValidationError("Automation run cancellation id requires a non-empty run_id.")
    return build_soai_id(("task", "automation", "run", normalized_run_id))


def build_automation_turn_request_id(run_id: str, turn_index: int) -> str:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValidationError("Automation turn request id requires a non-empty run_id.")
    normalized_turn_index = int(turn_index)
    if normalized_turn_index < 0:
        raise ValidationError("Automation turn_index must be non-negative.")
    return build_soai_id(
        ("req", "automation", "run", normalized_run_id, "turn", str(normalized_turn_index)),
    )
