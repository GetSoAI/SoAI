"""SoAI - Execution failure classification models [backend/orchestrator/execution/failure_classification_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.error_types import ErrorType

__all__ = ("ExecutionFailureDetails",)


@dataclass(frozen=True, slots=True)
class ExecutionFailureDetails:
    user_message: str
    state_reason: str
    log_stack: bool
    error_type: ErrorType
    affects_plugin_health: bool
    allow_failover: bool
