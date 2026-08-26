"""SoAI - MCP utility tool: hardware_snapshot [backend/mcp/tools/hardware_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ServiceUnavailableError, StateError, ValidationError
from core.hardware.system_info_keys import SYSTEM_INFO_COMPONENT_KEYS
from core.mcp.argument_validation import (
    parse_string_or_unique_non_empty_string_list_value,
)
from mcp.tools.admin_privileges import require_admin_user
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_hardware_snapshot",)

_DEFAULT_COMPONENTS: tuple[str, ...] = ("uptime", "os", "cpu", "memory", "gpu")
_ALLOWED_COMPONENTS: tuple[str, ...] = SYSTEM_INFO_COMPONENT_KEYS


def _parse_components(value: JSONValue | None) -> list[str]:
    return parse_string_or_unique_non_empty_string_list_value(
        value,
        default=_DEFAULT_COMPONENTS,
        allowed_values=_ALLOWED_COMPONENTS,
        build_error=ValidationError,
        list_message="components must be a string or an array of strings.",
        entry_message="components entries must be strings.",
        empty_message="components must contain at least one entry.",
        unknown_message=lambda component: f"Unknown component '{component}'.",
    )


def _parse_bool(value: JSONValue | None, *, default: bool) -> bool:
    return parse_bool_strict_default(
        value,
        field_name="Boolean parameter",
        default=default,
        message="Boolean parameter must be true or false.",
    )


def _sanitize_gpu_payload(
    gpu_payload: JSONValue,
    *,
    include_processes: bool,
) -> JSONValue:
    if not isinstance(gpu_payload, Mapping):
        return gpu_payload
    sanitized: JSONDict = {}
    for key, value in gpu_payload.items():
        if key == "by_device_id":
            continue
        if key != "gpus":
            if isinstance(key, str):
                sanitized[key] = value
            continue
        if not isinstance(value, list):
            sanitized["gpus"] = []
            continue
        sanitized_gpus: list[JSONDict] = []
        for entry in value:
            if not isinstance(entry, Mapping):
                continue
            gpu_entry: JSONDict = {}
            for gpu_key, gpu_value in entry.items():
                if not isinstance(gpu_key, str):
                    continue
                if gpu_key == "processes" and include_processes is False:
                    gpu_entry["processes"] = []
                    continue
                gpu_entry[gpu_key] = gpu_value
            if include_processes is False and "processes" not in gpu_entry:
                gpu_entry["processes"] = []
            sanitized_gpus.append(gpu_entry)
        sanitized["gpus"] = sanitized_gpus
    return sanitized


def _build_disk_space_snapshot(utility_tools: MCPUtilityToolsProtocol) -> JSONDict:
    base_path = utility_tools.config.get_str("SYSTEM.PATHS.BASE")
    if not isinstance(base_path, str) or not base_path.strip():
        raise StateError("SYSTEM.PATHS.BASE must be configured for soai_disk_space.")
    normalized_base_path = os.path.abspath(base_path)
    snapshot = utility_tools.storage_manager.snapshot_disk_space(normalized_base_path)
    mount_point = snapshot.mount_point
    percent_used = snapshot.percent_used
    return {
        "path": normalized_base_path,
        "mount_point": mount_point,
        "total_bytes": int(snapshot.total_bytes),
        "free_bytes": int(snapshot.free_bytes),
        "used_bytes": int(snapshot.used_bytes),
        "percent_used": float(percent_used) if percent_used is not None else None,
    }


def _extract_cpu_view(snapshot: Mapping[str, JSONValue]) -> JSONValue:
    cpu_value = snapshot.get("cpu")
    if isinstance(cpu_value, Mapping):
        return dict(cpu_value)
    cpus_value = snapshot.get("cpus")
    if isinstance(cpus_value, list) and cpus_value:
        first = cpus_value[0]
        if isinstance(first, Mapping):
            return dict(first)
    return {}


async def tool_hardware_snapshot(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONValue:
    hardware_manager = utility_tools.hardware_manager
    if hardware_manager is None or hardware_manager.enabled is False:
        raise ServiceUnavailableError("Hardware manager is not available.")

    components = _parse_components(arguments.get("components"))
    include_processes = _parse_bool(arguments.get("include_processes"), default=False)

    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="hardware_snapshot",
        message="User authentication required for hardware_snapshot.",
    )
    if include_processes:
        await require_admin_user(
            utility_tools,
            user_id=user_id,
            tool_name="hardware_snapshot include_processes=true",
        )

    snapshot_value = await hardware_manager.get_system_info(components=components, cache=False)
    if not isinstance(snapshot_value, Mapping):
        raise MCPToolError(-32603, "Hardware manager returned an invalid snapshot.")
    snapshot: Mapping[str, JSONValue] = snapshot_value

    response: JSONDict = {}
    timestamp_ms = snapshot.get("timestamp_ms")
    if isinstance(timestamp_ms, int):
        response["timestamp_ms"] = int(timestamp_ms)
    response["soai_disk_space"] = _build_disk_space_snapshot(utility_tools)

    for key in ("summary", "capabilities", "uptime", "os", "memory", "swap"):
        if key in snapshot:
            response[key] = snapshot[key]
    if "cpu" in components:
        response["cpu"] = _extract_cpu_view(snapshot)
    if "gpu" in snapshot:
        response["gpu"] = _sanitize_gpu_payload(
            snapshot.get("gpu"),
            include_processes=include_processes,
        )
    for component in components:
        if component in {"cpu", "gpu"}:
            continue
        if component in response:
            continue
        if component in snapshot:
            response[component] = snapshot[component]

    response["components"] = components
    response["include_processes"] = include_processes
    return response
