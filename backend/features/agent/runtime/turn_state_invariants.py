"""SoAI - Agent turn lifecycle invariants [backend/features/agent/runtime/turn_state_invariants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "normalize_active_inference_cancellation_id",
    "normalize_turn_start_inputs",
)


def normalize_active_inference_cancellation_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_turn_start_inputs(
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    mode: str,
    max_iterations: int,
    turn_cancellation_id: str,
    initial_active_inference_cancellation_id: str | None,
) -> tuple[str, int, str, str, int, str, str | None]:
    if not conv_id.strip():
        raise ValidationError("Agent turn conv_id is required.")
    if int(user_id) <= 0:
        raise ValidationError("Agent turn user_id is invalid.")
    if not turn_id.strip():
        raise ValidationError("Agent turn turn_id is required.")
    if not mode.strip():
        raise ValidationError("Agent turn mode is required.")
    if int(max_iterations) <= 0:
        raise ValidationError("Agent turn max_iterations is invalid.")
    if not turn_cancellation_id.strip():
        raise ValidationError("Agent turn turn_cancellation_id is required.")
    return (
        conv_id.strip(),
        int(user_id),
        turn_id.strip(),
        mode.strip(),
        int(max_iterations),
        turn_cancellation_id.strip(),
        normalize_active_inference_cancellation_id(initial_active_inference_cancellation_id),
    )
