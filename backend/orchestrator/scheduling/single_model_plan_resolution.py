"""SoAI - Single-model scheduler plan resolution [backend/orchestrator/scheduling/single_model_plan_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.model_info_fields import coerce_plugin_name
from core.orchestrator.execution_plan import (
    EXECUTION_PLAN_FAILURE_INVALID_REQUEST,
    EXECUTION_PLAN_STATUS_AVAILABLE,
    EXECUTION_PLAN_STATUS_ON_COOLDOWN,
    EXECUTION_PLAN_STATUS_UNAVAILABLE,
    ExecutionPlan,
)
from orchestrator.scheduling.requirement_failure_reasons import (
    format_requirements_failure_reason,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from orchestrator.scheduling.dependencies import SchedulerPlanningDependencies
    from orchestrator.scheduling.model_eligibility import ModelEligibilityEvaluator
    from orchestrator.scheduling.plugin_requirements import RequirementEvaluation

__all__ = ("resolve_single_model_execution_plan",)


async def resolve_single_model_execution_plan(
    *,
    deps: SchedulerPlanningDependencies,
    eligibility: ModelEligibilityEvaluator,
    model_name: str,
    excluded: set[str],
    requirements: dict[str, tuple[str, ...]],
) -> ExecutionPlan:
    status, model_info, evaluation = await eligibility.evaluate(
        model_name,
        excluded,
        requirements,
    )
    if status == "eligible" and model_info:
        universal_id_value = model_info.get("universal_id")
        universal_id = (
            universal_id_value
            if isinstance(universal_id_value, str) and universal_id_value
            else model_name
        )
        return _build_available_plan(universal_id)
    if status == "on_cooldown":
        resolved_universal_id = await deps.model_resolution_service.model_resolve_to_universal_id(
            model_name,
        )
        return _build_cooldown_plan(resolved_universal_id or model_name)
    if status == "unsupported":
        return _build_unsupported_plan(
            model_label=model_name,
            model_info=model_info,
            evaluation=evaluation,
            requirements=requirements,
        )
    resolved_universal_id = await deps.model_resolution_service.model_resolve_to_universal_id(
        model_name,
    )
    if resolved_universal_id:
        return await _resolve_universal_id_plan(
            eligibility=eligibility,
            resolved_universal_id=resolved_universal_id,
            excluded=excluded,
            requirements=requirements,
        )
    return _build_unavailable_plan()


async def _resolve_universal_id_plan(
    *,
    eligibility: ModelEligibilityEvaluator,
    resolved_universal_id: str,
    excluded: set[str],
    requirements: dict[str, tuple[str, ...]],
) -> ExecutionPlan:
    status, model_info, evaluation = await eligibility.evaluate(
        resolved_universal_id,
        excluded,
        requirements,
    )
    if status == "eligible" and model_info:
        return _build_available_plan(resolved_universal_id)
    if status == "on_cooldown":
        return _build_cooldown_plan(resolved_universal_id)
    if status == "unsupported":
        return _build_unsupported_plan(
            model_label=resolved_universal_id,
            model_info=model_info,
            evaluation=evaluation,
            requirements=requirements,
        )
    return _build_unavailable_plan()


def _build_unavailable_plan() -> ExecutionPlan:
    return {
        "universal_ids_to_try": [],
        "parameter_overrides": {},
        "virtual_model_name": None,
        "deferral_key": None,
        "status": EXECUTION_PLAN_STATUS_UNAVAILABLE,
    }


def _build_available_plan(universal_id: str) -> ExecutionPlan:
    plan = _build_unavailable_plan()
    plan["universal_ids_to_try"] = [universal_id]
    plan["status"] = EXECUTION_PLAN_STATUS_AVAILABLE
    return plan


def _build_cooldown_plan(deferral_key: str) -> ExecutionPlan:
    plan = _build_unavailable_plan()
    plan["deferral_key"] = deferral_key
    plan["status"] = EXECUTION_PLAN_STATUS_ON_COOLDOWN
    return plan


def _build_unsupported_plan(
    *,
    model_label: str,
    model_info: dict[str, JSONValue] | None,
    evaluation: RequirementEvaluation | None,
    requirements: dict[str, tuple[str, ...]],
) -> ExecutionPlan:
    plugin_name = coerce_plugin_name(model_info if isinstance(model_info, dict) else None)
    plan = _build_unavailable_plan()
    plan["failure_error_type"] = EXECUTION_PLAN_FAILURE_INVALID_REQUEST
    plan["failure_reason"] = format_requirements_failure_reason(
        model_label=model_label,
        plugin_name=plugin_name,
        missing_capabilities=evaluation.missing_capabilities if evaluation else (),
        missing_modalities=evaluation.missing_modalities if evaluation else (),
        required_capabilities=requirements["capabilities"],
        required_modalities=requirements["modalities"],
    )
    return plan
