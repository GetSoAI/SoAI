"""SoAI - Model context creation and task configuration logging [backend/orchestrator/lifecycle/task_tracking/model_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.redaction import redact_value
from core.logging.trace import TraceLogger
from core.models.model_context import ModelContext
from core.models.model_info_fields import coerce_plugin_name
from core.models.parameter_context import (
    classify_parameters_and_build_fingerprint,
    resolve_context_effective_parameters,
    resolve_context_startup_parameters,
)
from core.models.protocols import ParameterManagerProtocol
from core.models.source_identifier import require_source_model_id
from core.openai.upstream_request_customization import (
    SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER,
    summarize_openai_request_customization_for_log,
)
from core.tasks.task import Task
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_model_context",
    "build_startup_model_context",
    "resolve_model_source_id",
    "resolve_model_universal_id",
    "write_task_configuration_log",
)


def resolve_model_universal_id(task: Task, model_info: Mapping[str, JSONValue]) -> str:
    universal_id_raw = model_info.get("universal_id")
    if isinstance(universal_id_raw, str) and universal_id_raw:
        return universal_id_raw
    context = task.require_orchestration_context()
    for execution_universal_id in context.execution_universal_ids:
        if isinstance(execution_universal_id, str) and execution_universal_id:
            return execution_universal_id
    raise StateError("Model info missing universal_id.")


def resolve_model_source_id(model_info: Mapping[str, JSONValue]) -> str:
    return require_source_model_id(dict(model_info))


def _build_model_context_with_parameters(
    task: Task,
    model_info: Mapping[str, JSONValue],
    parameters: Mapping[str, JSONValue],
) -> ModelContext:
    plugin_raw = coerce_plugin_name(dict(model_info))
    if plugin_raw is None:
        raise StateError("Model info missing plugin.")
    universal_id = resolve_model_universal_id(task, model_info)
    model_path_value = model_info.get("path")
    model_path = model_path_value if isinstance(model_path_value, str) else None
    return ModelContext(
        universal_id=universal_id,
        source_model_id=resolve_model_source_id(model_info),
        plugin=plugin_raw,
        model_path=model_path,
        parameters=dict(parameters),
    )


def build_model_context(task: Task, model_info: Mapping[str, JSONValue]) -> ModelContext:
    context = task.require_orchestration_context()
    effective_parameters = resolve_context_effective_parameters(context)
    return _build_model_context_with_parameters(task, model_info, effective_parameters)


def build_startup_model_context(task: Task, model_info: Mapping[str, JSONValue]) -> ModelContext:
    context = task.require_orchestration_context()
    startup_parameters = resolve_context_startup_parameters(context)
    return _build_model_context_with_parameters(task, model_info, startup_parameters)


async def write_task_configuration_log(
    task: Task,
    model_info: Mapping[str, JSONValue],
    *,
    param_manager: ParameterManagerProtocol,
    tool_name_extractor: Callable[[list[JSONValue]], list[str]],
    logger: TraceLogger,
) -> None:
    context = task.require_orchestration_context()
    event = context.event
    trace_id = task.task_id
    if event is not None:
        trace_id_value = event.context.trace_id
        if isinstance(trace_id_value, str) and trace_id_value:
            trace_id = trace_id_value
    plugin_value = coerce_plugin_name(dict(model_info))
    if plugin_value is None:
        raise StateError("Model info missing plugin.")
    plugin_name = plugin_value
    model_id = resolve_model_source_id(model_info)
    final_params = resolve_context_effective_parameters(context)
    tool_count = 0
    if isinstance(final_params, dict):
        tools_value = final_params.get("tools")
        if isinstance(tools_value, list):
            tool_count = len(tool_name_extractor(tools_value))
    startup_params, inference_params, _fingerprint = (
        await classify_parameters_and_build_fingerprint(
            param_manager=param_manager,
            plugin_name=plugin_name,
            parameter_values=final_params,
        )
    )
    logger.info("*" * 80)
    logger.info(
        "%s",
        f" Executing on {plugin_name.upper()} with model: {model_id}[Trace: {trace_id}] ".center(
            80,
            "*",
        ),
    )
    logger.info("  Tools in request: %s", tool_count)
    parameter_definitions, all_categories = await param_manager.get_parameter_schema_snapshot(
        plugin_name,
    )

    def log_section(title: str, params_to_log: Mapping[str, JSONValue]) -> None:
        logger.info("  %s:", title)
        if not params_to_log:
            logger.info("    None")
            return
        categorized: dict[str, dict[str, JSONValue]] = defaultdict(dict)
        for name, value in params_to_log.items():
            parameter_definition_value = parameter_definitions.get(name)
            parameter_definition = (
                parameter_definition_value if is_json_dict(parameter_definition_value) else {}
            )
            category_value = parameter_definition.get("category")
            category_key = category_value if isinstance(category_value, str) else "other"
            categorized[category_key][name] = value
        for cat_key, cat_params in sorted(categorized.items()):
            cat_info = all_categories.get(cat_key, {})
            default_title = cat_key.replace("_", " ").capitalize()
            cat_title = (
                cat_info.get("title", default_title)
                if isinstance(cat_info, dict)
                else default_title
            )
            logger.info("    %s:", cat_title)
            for param_key, param_value in sorted(cat_params.items()):
                if param_key == "tools" and isinstance(param_value, list):
                    tool_count = len(tool_name_extractor(param_value))
                    logger.info(
                        "      - %s: %s",
                        param_key,
                        f"{tool_count} tool(s)",
                    )
                    continue
                if param_key == SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER:
                    logger.info(
                        "      - %s: %s",
                        param_key,
                        summarize_openai_request_customization_for_log(param_value),
                    )
                    continue
                logger.info(
                    "      - %s: %s",
                    param_key,
                    redact_value(param_key, param_value),
                )

    log_section("Startup Parameters (Snapshotted)", startup_params)
    logger.info("  %s", "=" * 76)
    log_section("Inference Parameters (Live)", inference_params)
    logger.info("*" * 80)
