"""SoAI - Runtime state transition validation helpers [backend/orchestrator/lifecycle/state_transition_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SoAIError

__all__ = ("is_invalid_transition_error",)

OPERATION_BEGIN_RUNTIME_TRANSITION = (
    "authoritative_plugin_state_transitions.begin_runtime_transition"
)


def is_invalid_transition_error(exception: BaseException) -> bool:
    if not isinstance(exception, SoAIError):
        return False
    if exception.operation != OPERATION_BEGIN_RUNTIME_TRANSITION:
        return False
    details = exception.details or {}
    return bool("previous_state" in details and "new_state" in details)
