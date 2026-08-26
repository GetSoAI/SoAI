"""SoAI - Exact model-target prompt token counting [backend/features/openai/model_prompt_token_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import PayloadTooLargeError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.model_context import ModelContext
from core.models.model_info_fields import coerce_plugin_name, is_model_info_active_and_enabled
from core.models.parameter_request_overrides import extract_payload_request_overrides
from core.models.provider_backing import is_provider_backed_model
from core.models.source_identifier import require_source_model_id
from core.openai.token_accounting import PromptOccupancy
from core.plugins.prompt_token_counting import parse_plugin_prompt_token_count_result
from core.types.json import is_json_dict
from core.types.json_value import copy_json_dict

if TYPE_CHECKING:
    from core.models.protocols import ModelInformationServiceProtocol, ModelParameterServiceProtocol
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorLifecycleProtocol,
        PluginStateProtocol,
    )
    from core.plugins.protocols import PluginManagerProtocol
    from core.runtime.request_context import RequestContext
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict

__all__ = ("ModelPromptCountTarget", "count_target_plugin_prompt_occupancy")

LOGGER_NAME = "SoAI.features.openai.model_prompt_token_targets"
OPERATION = "openai.prompt_tokens.plugin_count"
PLUGIN_COUNT_RECOVERABLE_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (PayloadTooLargeError,)


@dataclass(frozen=True, slots=True)
class ModelPromptCountTarget:
    universal_id: str
    model_info: JSONDict
    plugin_name: str


def build_model_prompt_count_targets(
    universal_ids: tuple[str, ...],
    model_records: tuple[JSONDict, ...] | None,
) -> tuple[ModelPromptCountTarget, ...]:
    if model_records is None or len(universal_ids) != len(model_records):
        return ()
    targets: list[ModelPromptCountTarget] = []
    for universal_id, model_info in zip(universal_ids, model_records, strict=True):
        if not is_model_info_active_and_enabled(model_info):
            return ()
        plugin_name = coerce_plugin_name(model_info)
        if plugin_name is None:
            return ()
        targets.append(ModelPromptCountTarget(universal_id, model_info, plugin_name))
    return tuple(targets)


async def count_target_plugin_prompt_occupancy(
    *,
    target: ModelPromptCountTarget,
    plugin_payload: JSONDict,
    request_payload: JSONDict,
    model_information_service: ModelInformationServiceProtocol,
    model_parameter_service: ModelParameterServiceProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    request_context: RequestContext,
) -> PromptOccupancy | None:
    plugin = await plugin_manager.get_plugin_instance(target.plugin_name)
    if plugin is None or not plugin.SUPPORTS_PROMPT_TOKEN_COUNTING:
        return None
    state_version_before = await state_aggregator.get_state_version()
    states_before = await orchestrator_lifecycle.watchers.get_plugin_states_snapshot(
        {target.plugin_name},
    )
    if not _target_is_countable(target, states_before.get(target.plugin_name)):
        return None
    model_context, parameter_version_before = await _build_model_context(
        request_payload=request_payload,
        target=target,
        model_parameter_service=model_parameter_service,
    )
    try:
        result_payload = await plugin.count_prompt_tokens(
            plugin_payload,
            request_context,
            model_context,
        )
    except PLUGIN_COUNT_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Plugin prompt token counting failed; using conservative estimation.",
            operation=OPERATION,
            trace_id=request_context.trace_id,
            details={"plugin_name": target.plugin_name, "universal_id": target.universal_id},
        )
        return None
    result = parse_plugin_prompt_token_count_result(result_payload)
    if result.precision != "exact" or result.prompt_tokens is None:
        return None
    state_version_after = await state_aggregator.get_state_version()
    states_after = await orchestrator_lifecycle.watchers.get_plugin_states_snapshot(
        {target.plugin_name},
    )
    _parameters_after, parameter_version_after = (
        await model_parameter_service.model_get_parameters_and_version(target.universal_id)
    )
    model_info_after = await model_information_service.model_get_info(target.universal_id)
    if (
        state_version_before != state_version_after
        or parameter_version_before != parameter_version_after
        or model_info_after != target.model_info
        or not _target_is_countable(target, states_after.get(target.plugin_name))
    ):
        return None
    return PromptOccupancy(result.prompt_tokens, False, None, "exact")


def _target_is_countable(
    target: ModelPromptCountTarget,
    plugin_state: PluginStateProtocol | None,
) -> bool:
    if is_provider_backed_model(target.model_info):
        return True
    if plugin_state is None:
        return False
    return plugin_state.loaded_model_universal_id == target.universal_id


async def _build_model_context(
    *,
    request_payload: JSONDict,
    target: ModelPromptCountTarget,
    model_parameter_service: ModelParameterServiceProtocol,
) -> tuple[ModelContext, int]:
    parameter_values, parameter_version = (
        await model_parameter_service.model_get_parameters_and_version(target.universal_id)
    )
    definitions = await model_parameter_service.model_get_parameter_definitions(target.universal_id)
    parameters = copy_json_dict(parameter_values)
    parameters.update(
        extract_payload_request_overrides(
            payload=request_payload,
            parameter_definitions=definitions,
        ),
    )
    model_path_value = target.model_info.get("path")
    provider_details = target.model_info.get("provider_details")
    return (
        ModelContext(
            universal_id=target.universal_id,
            source_model_id=require_source_model_id(target.model_info),
            plugin=target.plugin_name,
            model_path=model_path_value if isinstance(model_path_value, str) else None,
            parameters=parameters,
            provider_details=(
                copy_json_dict(provider_details) if is_json_dict(provider_details) else None
            ),
        ),
        parameter_version,
    )
