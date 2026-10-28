"""SoAI - Execution plan payload types for orchestrator scheduling [backend/core/orchestrator/execution_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict

from core.errors.exceptions import ValidationError
from core.errors.public_projection import apply_public_error_payload
from core.openai.request_requirement_failures import (
    OpenAIRequestRequirementMismatch,
    build_openai_request_requirement_public_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "DEFAULT_NO_VALID_MODELS_REASON",
    "DEFAULT_NO_VIRTUAL_MODELS_REASON",
    "EXECUTION_PLAN_FAILURE_INVALID_REQUEST",
    "EXECUTION_PLAN_STATUS_AVAILABLE",
    "EXECUTION_PLAN_STATUS_ON_COOLDOWN",
    "EXECUTION_PLAN_STATUS_UNAVAILABLE",
    "ExecutionPlan",
    "resolve_execution_plan_failure_reason",
    "resolve_execution_plan_validation_error",
)

EXECUTION_PLAN_STATUS_AVAILABLE: Final = "AVAILABLE"
EXECUTION_PLAN_STATUS_ON_COOLDOWN: Final = "ON_COOLDOWN"
EXECUTION_PLAN_STATUS_UNAVAILABLE: Final = "UNAVAILABLE"
EXECUTION_PLAN_FAILURE_INVALID_REQUEST: Final = "invalid_request"
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
    requirement_mismatch: NotRequired[OpenAIRequestRequirementMismatch]


def resolve_execution_plan_validation_error(plan: ExecutionPlan) -> ValidationError | None:
    if (
        plan["status"] != EXECUTION_PLAN_STATUS_UNAVAILABLE
        or plan.get("failure_error_type") != EXECUTION_PLAN_FAILURE_INVALID_REQUEST
    ):
        return None
    failure_reason = plan.get("failure_reason")
    if not isinstance(failure_reason, str) or not failure_reason:
        return None
    error = ValidationError(failure_reason, details={"param": "model"})
    mismatch = plan.get("requirement_mismatch")
    if mismatch is not None:
        apply_public_error_payload(error, build_openai_request_requirement_public_error(mismatch))
    return error


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
