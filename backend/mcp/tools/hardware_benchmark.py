"""SoAI - MCP internal utility tool: hardware_benchmark [backend/mcp/tools/hardware_benchmark.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_limits import (
    SOAIBENCH_HISTORY_DEFAULT_LIMIT,
    SOAIBENCH_LIST_MAX_LIMIT,
    SOAIBENCH_LIST_MIN_LIMIT,
    SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS,
    SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS,
)
from core.logging.trace import get_logger
from core.tool_calls.deferred_tool_call_streamer import (
    DeferredToolCallActivity,
    DeferredToolCallDependencies,
)
from core.types.json_value import JSONValue, coerce_json_dict, copy_json_dict
from mcp.tools.admin_privileges import require_admin_user
from mcp.tools.argument_fields import require_non_empty_string, require_string_choice
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.argument_scalars import parse_clamped_int, parse_optional_number_strict
from mcp.tools.hardware_internal_context import (
    require_hardware_internal_execute_context,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_hardware_benchmark",)

_LOGGER_NAME = "SoAI.mcp.tools.hardware_benchmark"


async def tool_hardware_benchmark(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    action = _parse_action(arguments)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="hardware_benchmark",
        message="User authentication required for hardware_benchmark.",
    )
    await require_admin_user(utility_tools, user_id=user_id, tool_name="hardware_benchmark")
    require_hardware_internal_execute_context(utility_tools, tool_name="hardware_benchmark")
    if action == "start":
        profile = _required_profile(arguments)
        result = await utility_tools.hardware_soaibench.start_run(
            device_id=require_non_empty_string(arguments.get("device_id"), key="device_id"),
            profile=_service_profile_for_tool_profile(profile),
            benchmark_mode=_benchmark_mode_for_tool_profile(profile),
            created_by_user_id=user_id,
            created_by_tool="hardware_benchmark",
            temperature_limit_celsius=_optional_float(arguments, "temperature_limit_celsius"),
            deferred_tool_activity=_build_deferred_tool_activity(utility_tools),
        )
        return _tool_response_for_service_response(result)
    if action == "status":
        result = await utility_tools.hardware_soaibench.get_run(
            run_id=require_non_empty_string(arguments.get("run_id"), key="run_id"),
            user_id=user_id,
        )
        return _tool_response_for_service_response(result)
    if action == "stop":
        result = await utility_tools.hardware_soaibench.stop_run(
            run_id=require_non_empty_string(arguments.get("run_id"), key="run_id"),
            user_id=user_id,
        )
        return _tool_response_for_service_response(result)
    if action == "history":
        result = await utility_tools.hardware_soaibench.list_history(
            device_id=require_non_empty_string(arguments.get("device_id"), key="device_id"),
            user_id=user_id,
            limit=_optional_int(
                arguments,
                "history_limit",
                default=SOAIBENCH_HISTORY_DEFAULT_LIMIT,
            ),
        )
        return _tool_response_for_service_response(result)
    raise ValidationError(f"Unsupported hardware_benchmark action: {action}")


def _parse_action(arguments: JSONDict) -> str:
    return require_string_choice(
        arguments.get("action"),
        key="action",
        choices=("start", "status", "stop", "history"),
    )


def _optional_float(arguments: JSONDict, key: str) -> float | None:
    return parse_optional_number_strict(
        arguments.get(key),
        field_name=key,
        min_value=SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS,
        max_value=SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS,
    )


def _required_profile(arguments: JSONDict) -> str:
    return require_string_choice(
        arguments.get("profile"),
        key="profile",
        choices=("soaibench", "stress_test"),
    )


def _service_profile_for_tool_profile(profile: str) -> str:
    if profile == "soaibench":
        return "standard"
    return "stress"


def _benchmark_mode_for_tool_profile(profile: str) -> str | None:
    if profile == "soaibench":
        return "certified"
    return None


def _tool_profile_for_service_profile(profile: str) -> str:
    if profile == "standard":
        return "soaibench"
    if profile == "stress":
        return "stress_test"
    return profile


def _copy_run_with_tool_profile(run: JSONDict) -> JSONDict:
    mapped = copy_json_dict(run)
    profile = mapped.get("profile")
    if isinstance(profile, str):
        mapped["profile"] = _tool_profile_for_service_profile(profile)
    return mapped


def _copy_run_list_with_tool_profiles(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    mapped_runs: list[JSONDict] = []
    for item in value:
        run = coerce_json_dict(item)
        if run is not None:
            mapped_runs.append(_copy_run_with_tool_profile(run))
    return mapped_runs


def _tool_response_for_service_response(response: JSONDict) -> JSONDict:
    mapped = _copy_run_with_tool_profile(response)
    history = mapped.get("history")
    if isinstance(history, list):
        mapped["history"] = _copy_run_list_with_tool_profiles(history)
    runs = mapped.get("runs")
    if isinstance(runs, list):
        mapped["runs"] = _copy_run_list_with_tool_profiles(runs)
    return mapped


def _optional_int(arguments: JSONDict, key: str, *, default: int) -> int:
    return parse_clamped_int(
        arguments.get(key),
        field_name=key,
        default=default,
        min_value=SOAIBENCH_LIST_MIN_LIMIT,
        max_value=SOAIBENCH_LIST_MAX_LIMIT,
    )


def _build_deferred_tool_activity(
    utility_tools: MCPUtilityToolsProtocol,
) -> DeferredToolCallActivity | None:
    identity = utility_tools.active_tool_call_context.get(None)
    if identity is None:
        return None
    if identity.turn_id is None or identity.iteration_index is None:
        return None
    request_context = utility_tools.active_request_context.get(None)
    trace_id = request_context.trace_id if request_context is not None else ""
    return DeferredToolCallActivity(
        storage_call_id=identity.storage_call_id,
        streamer_deps=DeferredToolCallDependencies(
            database_tool_calls=utility_tools.database_tool_calls,
            event_bus=utility_tools.event_bus,
            logger=get_logger(_LOGGER_NAME),
            trace_id=trace_id,
            user_id=identity.user_id,
            conv_id=identity.conv_id,
            assistant_turn_at_ms=identity.assistant_turn_at_ms,
            model_variant_index=identity.model_variant_index,
            turn_id=identity.turn_id,
            iteration_index=int(identity.iteration_index),
            call_id=identity.call_id,
            tool_name="hardware_benchmark",
        ),
    )
