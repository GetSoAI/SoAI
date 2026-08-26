"""SoAI - Plugin system capability compatibility reporting [backend/plugins/state/system_capability_report.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.protocols import GetGpuInfoCallable
from core.logging.trace import get_logger
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.capability_normalization import (
    as_json_list,
    normalize_required_capabilities,
)
from plugins.state.capability_platform_validators import (
    validate_arch_capability,
    validate_os_capability,
    validate_platform_capability,
)
from plugins.state.capability_validators import (
    CapabilityValidationResult,
    to_detail_dict,
    validate_drivers_capability,
    validate_gpu_capability,
    validate_gpu_features_capability,
)
from plugins.state.host_snapshot import get_host_capability_snapshot

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_system_capability_report",)

LOGGER_NAME = "SoAI.plugins.state.system_capability_report"
OPERATION = "plugins.state.system_capability_report.coerce_user_override_flag"


async def build_system_capability_report(
    manager: PluginManagerRuntimeProtocol | None,
    plugin_name: str,
    required_value: JSONValue,
    existing_record: JSONDict | None,
    get_gpu_info: GetGpuInfoCallable,
    host_snapshot: JSONDict | None = None,
) -> JSONDict:
    raw_required, normalized_required = normalize_required_capabilities(
        required_value if required_value is not None else {},
    )
    if host_snapshot is None:
        host_snapshot = await get_host_capability_snapshot(
            manager,
            get_gpu_info,
            include_gpu_inventory=True,
        )
    messages: list[JSONValue] = []
    details: list[JSONValue] = []
    blocking_actions: list[JSONValue] = []
    report: JSONDict = {
        "plugin": plugin_name,
        "required": {key: as_json_list(value) for key, value in raw_required.items()},
        "normalized": {key: as_json_list(value) for key, value in normalized_required.items()},
        "host": host_snapshot,
        "messages": messages,
        "status": "supported",
        "details": details,
        "user_override": coerce_bool_with_recovery(
            existing_record or {},
            "user_enabled_once",
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION,
            default=False,
            recover_message="Failed to parse user_enabled_once flag (non-critical).",
        ),
        "blocking_actions": blocking_actions,
    }
    validation_results: list[CapabilityValidationResult | None] = [
        validate_gpu_capability(
            normalized_required.get("gpu"),
            raw_required.get("gpu", []),
            host_snapshot,
        ),
        validate_platform_capability(
            normalized_required.get("platforms") or normalized_required.get("platform"),
            raw_required.get("platforms", []) or raw_required.get("platform", []),
            host_snapshot,
        ),
        validate_os_capability(
            normalized_required.get("os"),
            raw_required.get("os", []),
            host_snapshot,
        ),
        validate_arch_capability(
            normalized_required.get("arch"),
            raw_required.get("arch", []),
            host_snapshot,
        ),
        validate_gpu_features_capability(
            normalized_required.get("gpu_features"),
            raw_required.get("gpu_features", []),
            host_snapshot,
        ),
        validate_drivers_capability(
            normalized_required.get("drivers"),
            raw_required.get("drivers", []),
            host_snapshot,
        ),
    ]
    for result in validation_results:
        if result is not None and not result.is_valid:
            if report["status"] == "supported":
                report["status"] = "unsupported"
            messages.append(result.message)
            details.append(to_detail_dict(result))
    if report["status"] != "supported":
        blocking_actions.extend(["install_backend", "update_backend", "download_model"])
    return report
