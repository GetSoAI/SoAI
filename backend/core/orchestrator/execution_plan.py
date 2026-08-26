"""SoAI - Execution plan payload types for orchestrator scheduling [backend/core/orchestrator/execution_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "DEFAULT_NO_VALID_MODELS_REASON",
    "DEFAULT_NO_VIRTUAL_MODELS_REASON",
    "EXECUTION_PLAN_FAILURE_INVALID_REQUEST",
    "EXECUTION_PLAN_FAILURE_SERVER_ERROR",
    "EXECUTION_PLAN_STATUS_AVAILABLE",
    "EXECUTION_PLAN_STATUS_ON_COOLDOWN",
    "EXECUTION_PLAN_STATUS_UNAVAILABLE",
    "ExecutionPlan",
    "resolve_execution_plan_failure_reason",
)

EXECUTION_PLAN_STATUS_AVAILABLE: Final = "AVAILABLE"
EXECUTION_PLAN_STATUS_ON_COOLDOWN: Final = "ON_COOLDOWN"
EXECUTION_PLAN_STATUS_UNAVAILABLE: Final = "UNAVAILABLE"
EXECUTION_PLAN_FAILURE_INVALID_REQUEST: Final = "invalid_request"
EXECUTION_PLAN_FAILURE_SERVER_ERROR: Final = "server_error"
DEFAULT_NO_VALID_MODELS_REASON: Final[str] = "No valid, active models found for task"
DEFAULT_NO_VIRTUAL_MODELS_REASON: Final[str] = "No models available for virtual model."


class ExecutionPlan(TypedDict):
    universal_ids_to_try: list[str]
    parameter_overrides: dict[str, dict[str, JSONValue]]
    virtual_model_name: str | None
    deferral_key: str | None
    status: Literal["AVAILABLE", "ON_COOLDOWN", "UNAVAILABLE"]
    failure_reason: NotRequired[str]
    failure_error_type: NotRequired[Literal["invalid_request", "server_error"]]


def resolve_execution_plan_failure_reason(
    plan: ExecutionPlan,
    *,
    default_reason: str,
) -> str:
    failure_reason = plan.get("failure_reason")
    failure_error_type = plan.get("failure_error_type")
    if (
        failure_error_type == EXECUTION_PLAN_FAILURE_INVALID_REQUEST
        and isinstance(failure_reason, str)
        and failure_reason
    ):
        return failure_reason
    return default_reason
