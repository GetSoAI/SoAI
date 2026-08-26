"""SoAI - Orchestrator queueing parameter snapshot building [backend/orchestrator/queueing/parameter_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.models.model_info_fields import coerce_plugin_name
from core.models.parameter_context import classify_parameters_and_build_fingerprint
from core.models.parameter_request_overrides import extract_payload_request_overrides
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.orchestration_context import (
    OrchestrationContext,
    with_parameter_snapshot_state,
)
from core.tasks.orchestration_context_cache import merge_orchestration_context_snapshot
from core.tasks.task import Task
from core.types.json_value import copy_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_parameter_snapshot_state_to_context",
    "build_parameter_snapshot",
    "copy_parameter_overrides",
    "rebuild_requeued_parameter_state",
)


def copy_parameter_overrides(
    parameter_overrides: dict[str, dict[str, JSONValue]],
) -> dict[str, dict[str, JSONValue]]:
    return {
        universal_id: {
            param_key: copy_json_value(param_value) for param_key, param_value in overrides.items()
        }
        for universal_id, overrides in parameter_overrides.items()
    }


async def build_parameter_snapshot(
    queue: OrchestratorQueueProtocol,
    task: Task,
) -> tuple[JSONDict, int] | None:
    context = task.require_orchestration_context()
    if not context.execution_universal_ids:
        return None
    universal_id = context.execution_universal_ids[0]
    raw_params, version = (
        await queue.orchestrator_deps.model_parameter_service.model_get_parameters_and_version(
            universal_id,
        )
    )
    params = {
        param_key: copy_json_value(param_value) for param_key, param_value in raw_params.items()
    }
    params.update(
        {
            param_key: copy_json_value(param_value)
            for param_key, param_value in context.parameter_overrides.get(universal_id, {}).items()
        },
    )
    return (params, version)


async def apply_parameter_snapshot_state_to_context(
    *,
    queue: OrchestratorQueueProtocol,
    task: Task,
    context: OrchestrationContext,
    plugin_name: str | None,
) -> OrchestrationContext:
    parameter_snapshot = await build_parameter_snapshot(queue, task)
    startup_params: dict[str, JSONValue] = {}
    inference_params: dict[str, JSONValue] = {}
    parameter_version: int | None = None
    startup_param_fingerprint: str | None = None
    if parameter_snapshot is not None:
        parameter_values, parameter_version = parameter_snapshot
        if plugin_name is not None:
            parameter_definitions = (
                await queue.orchestrator_deps.param_manager.get_all_parameters_for_plugin(
                    plugin_name,
                )
            )
            event = context.event
            payload = event.payload if event is not None else None
            request_overrides = extract_payload_request_overrides(
                payload=payload if isinstance(payload, dict) else None,
                parameter_definitions=parameter_definitions,
            )
            if request_overrides:
                parameter_values.update(
                    {
                        param_key: copy_json_value(param_value)
                        for param_key, param_value in request_overrides.items()
                    },
                )
                parameter_snapshot = (parameter_values, parameter_version)
            await queue.orchestrator_deps.model_parameter_service.model_validate_parameters(
                context.execution_universal_ids[0],
                parameter_values,
            )
            (
                startup_params,
                inference_params,
                startup_param_fingerprint,
            ) = await classify_parameters_and_build_fingerprint(
                param_manager=queue.orchestrator_deps.param_manager,
                plugin_name=plugin_name,
                parameter_values=parameter_values,
            )
    return with_parameter_snapshot_state(
        context,
        parameter_snapshot=parameter_snapshot,
        startup_params=startup_params,
        inference_params=inference_params,
        parameter_version=parameter_version,
        startup_param_fingerprint=startup_param_fingerprint,
    )


async def rebuild_requeued_parameter_state(
    queue: OrchestratorQueueProtocol,
    task: Task,
) -> tuple[Task, tuple[JSONDict, int] | None]:
    context = task.require_orchestration_context()
    plugin_name: str | None = None
    if context.execution_universal_ids:
        model_info = await queue.orchestrator_deps.model_information_service.model_get_info(
            context.execution_universal_ids[0],
        )
        plugin_name = coerce_plugin_name(model_info if isinstance(model_info, dict) else None)
    updated_context = await apply_parameter_snapshot_state_to_context(
        queue=queue,
        task=task,
        context=context,
        plugin_name=plugin_name,
    )
    updated_context = replace(
        updated_context,
        plugin_name=plugin_name,
        routing_key=(
            context.execution_universal_ids[0]
            if context.execution_universal_ids
            else context.routing_key
        ),
    )
    updated_task = task.with_orchestration_context(updated_context)
    resolved_task = await merge_orchestration_context_snapshot(queue.task_registry, updated_task)
    return (resolved_task, updated_context.parameter_snapshot)
