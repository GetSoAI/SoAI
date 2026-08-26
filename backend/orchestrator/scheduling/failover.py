"""SoAI - Failover-aware scheduler planning and model eligibility [backend/orchestrator/scheduling/failover.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.orchestrator.execution_plan import (
    EXECUTION_PLAN_FAILURE_INVALID_REQUEST,
    EXECUTION_PLAN_STATUS_AVAILABLE,
    EXECUTION_PLAN_STATUS_ON_COOLDOWN,
    EXECUTION_PLAN_STATUS_UNAVAILABLE,
    ExecutionPlan,
)
from core.orchestrator.routing_config import ConstituentModelConfig
from core.tasks.orchestration_context import OrchestrationContext
from orchestrator.scheduling.dependencies import SchedulerPlanningDependencies
from orchestrator.scheduling.model_eligibility import ModelEligibilityEvaluator
from orchestrator.scheduling.plugin_requirements import RequirementEvaluation
from orchestrator.scheduling.requirement_failure_reasons import (
    format_virtual_model_requirements_failure_reason,
)
from orchestrator.scheduling.single_model_plan_resolution import (
    resolve_single_model_execution_plan,
)
from orchestrator.scheduling.virtual_model_candidate_scoring import (
    EligibleVirtualModelCandidate,
    order_load_balanced_virtual_model_candidates,
)

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = ("SchedulerPlanning",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.failover"
OPERATION_RESOLVE_EXECUTION_PLAN = "orchestrator.scheduler.resolve_execution_plan"


class SchedulerPlanning:
    def __init__(self, deps: SchedulerPlanningDependencies) -> None:
        self._deps = deps
        self._eligibility = ModelEligibilityEvaluator(deps)
        self._virtual_model_selection_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=2000,
                cleanup_interval_seconds=300.0,
            ),
        )

    async def resolve_execution_plan(
        self,
        task: Task,
        context: OrchestrationContext,
        excluded_universal_ids: set[str] | None = None,
    ) -> ExecutionPlan:
        try:
            task_context = task.orchestration_context
            if task_context is not None and task_context.tracking_id != context.tracking_id:
                raise StateError("Execution planning context does not match task tracking_id.")
            return await self._resolve_execution_plan(context, excluded_universal_ids)
        except asyncio.CancelledError:
            await self._deps.queue.execution_reservations.release(context.tracking_id)
            raise
        except Exception as exception:
            logger = get_logger(LOGGER_NAME)
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_RESOLVE_EXECUTION_PLAN,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to resolve execution plan.",
                operation=OPERATION_RESOLVE_EXECUTION_PLAN,
                details={"tracking_id": context.tracking_id},
            )
            await self._deps.queue.execution_reservations.release(context.tracking_id)
            raise

    async def _resolve_execution_plan(
        self,
        context: OrchestrationContext,
        excluded_universal_ids: set[str] | None = None,
    ) -> ExecutionPlan:
        event = context.event
        if event is None:
            raise StateError("Execution planning requires an inference event.")
        model_name_value = event.payload.get("model", "")
        model_name = model_name_value if isinstance(model_name_value, str) else ""
        plan: ExecutionPlan = {
            "universal_ids_to_try": [],
            "parameter_overrides": {},
            "virtual_model_name": None,
            "deferral_key": None,
            "status": EXECUTION_PLAN_STATUS_UNAVAILABLE,
        }
        excluded = excluded_universal_ids or set()
        requirements = {
            "capabilities": tuple(event.required_capabilities),
            "modalities": tuple(event.required_modalities),
        }
        virtual_model_map = await self._deps.lifecycle.startup.get_virtual_model_map()
        virtual_model_config = virtual_model_map.get(model_name)
        if virtual_model_config is not None:
            plan["virtual_model_name"] = model_name
            if await self._deps.virtual_model_health.in_stale_cooldown(model_name):
                plan["status"] = EXECUTION_PLAN_STATUS_ON_COOLDOWN
                plan["deferral_key"] = model_name
                await self._deps.queue.tracking.set_deferral_reason(
                    model_name,
                    f"Virtual model '{model_name}' is waiting to recover after repeated failures.",
                )
                await self._deps.queue.execution_reservations.release(context.tracking_id)
                return plan
            evaluation_tasks = [
                self._eligibility.evaluate(
                    model_entry.universal_id,
                    excluded,
                    requirements,
                )
                for model_entry in virtual_model_config.models
            ]
            evaluation_results = await asyncio.gather(*evaluation_tasks, return_exceptions=False)
            eligible_candidates: list[EligibleVirtualModelCandidate] = []
            on_cooldown = False
            unsupported_evaluations: list[RequirementEvaluation] = []
            for index, (status, info, evaluation) in enumerate(evaluation_results):
                if status == "on_cooldown":
                    on_cooldown = True
                if status == "unsupported" and evaluation is not None:
                    unsupported_evaluations.append(evaluation)
                if status == "eligible" and info:
                    eligible_candidates.append(
                        EligibleVirtualModelCandidate(
                            model_config=virtual_model_config.models[index],
                            model_info=info,
                            original_index=index,
                        ),
                    )
            if not eligible_candidates:
                plan["status"] = (
                    EXECUTION_PLAN_STATUS_ON_COOLDOWN
                    if on_cooldown
                    else EXECUTION_PLAN_STATUS_UNAVAILABLE
                )
                if on_cooldown:
                    plan["deferral_key"] = model_name
                elif (
                    requirements["capabilities"] or requirements["modalities"]
                ) and unsupported_evaluations:
                    plan["failure_error_type"] = EXECUTION_PLAN_FAILURE_INVALID_REQUEST
                    plan["failure_reason"] = format_virtual_model_requirements_failure_reason(
                        virtual_model_name=model_name,
                        required_capabilities=requirements["capabilities"],
                        required_modalities=requirements["modalities"],
                        evaluation_results=unsupported_evaluations,
                    )
                await self._deps.queue.execution_reservations.release(context.tracking_id)
                return plan
            if virtual_model_config.strategy == "load_balancing":
                async with self._virtual_model_selection_locks.lock(model_name):
                    all_models_ordered = await order_load_balanced_virtual_model_candidates(
                        self._deps,
                        model_name,
                        eligible_candidates,
                    )
                    _apply_ordered_virtual_models(plan, all_models_ordered)
                    await self._reserve_plan_primary(context, plan)
            else:
                async with self._virtual_model_selection_locks.lock(model_name):
                    all_models_ordered = [
                        candidate.model_config for candidate in eligible_candidates
                    ]
                    _apply_ordered_virtual_models(plan, all_models_ordered)
                    await self._reserve_plan_primary(context, plan)
        else:
            plan = await resolve_single_model_execution_plan(
                deps=self._deps,
                eligibility=self._eligibility,
                model_name=model_name,
                excluded=excluded,
                requirements=requirements,
            )
            await self._deps.queue.execution_reservations.release(context.tracking_id)
        return plan

    async def _reserve_plan_primary(
        self,
        context: OrchestrationContext,
        plan: ExecutionPlan,
    ) -> None:
        if plan["status"] != EXECUTION_PLAN_STATUS_AVAILABLE:
            await self._deps.queue.execution_reservations.release(context.tracking_id)
            return
        virtual_model_name = plan.get("virtual_model_name")
        universal_ids = plan["universal_ids_to_try"]
        if not isinstance(virtual_model_name, str) or not virtual_model_name or not universal_ids:
            await self._deps.queue.execution_reservations.release(context.tracking_id)
            return
        await self._deps.queue.execution_reservations.reserve(
            context.tracking_id,
            universal_ids[0],
        )


def _apply_ordered_virtual_models(
    plan: ExecutionPlan,
    models: list[ConstituentModelConfig],
) -> None:
    plan.update(
        {
            "universal_ids_to_try": [model_entry.universal_id for model_entry in models],
            "parameter_overrides": {
                model_entry.universal_id: model_entry.parameters
                for model_entry in models
                if model_entry.parameters
            },
            "status": EXECUTION_PLAN_STATUS_AVAILABLE,
        },
    )
