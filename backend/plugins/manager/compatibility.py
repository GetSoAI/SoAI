"""SoAI - Plugin compatibility evaluation and enforcement [backend/plugins/manager/compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.plugins.errors import PluginCapabilityError, PluginIncompatibleError
from core.serialization.json_parsing import parse_json_value
from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from core.state.state_names import ORCH_STATE_DISABLED
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.compatibility import (
    build_compatibility_info,
    should_block_for_incompatibility,
)
from plugins.state.publishing import require_plugin_record
from plugins.state.system_capability_report import build_system_capability_report

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "compatibility_from_record",
    "ensure_plugin_compatible",
    "ensure_record_is_compatible",
    "ensure_system_capabilities",
    "is_plugin_compatible",
)

LOGGER_NAME = "SoAI.plugins.manager.compatibility"
OPERATION_COMPATIBILITY_FROM_RECORD = "plugins.manager.compatibility.compatibility_from_record"


def compatibility_from_record(record: JSONDict) -> CompatibilityInfo:
    logger = get_logger(LOGGER_NAME)
    raw_reason = record.get("incompatibility_reason")
    try:
        reason = IncompatibilityReason(raw_reason) if raw_reason else None
    except ValueError:
        reason = None
    override_flag = coerce_bool_with_recovery(
        record,
        "incompatibility_override",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.manager.compatibility.coerce_compatibility_bool",
        default=False,
        recover_message="Failed to parse boolean flag from compatibility record (non-critical).",
    )
    details_raw = record.get("incompatibility_details")
    details: JSONDict = {}
    if isinstance(details_raw, str):
        try:
            loaded = parse_json_value(details_raw)
            if isinstance(loaded, dict):
                details = loaded
        except (ValidationError, TypeError) as parse_error:
            log_handled_exception(
                logger,
                parse_error,
                message="Failed to parse compatibility details JSON (non-critical).",
                operation=OPERATION_COMPATIBILITY_FROM_RECORD,
                details={"raw_value": details_raw},
            )
    elif isinstance(details_raw, dict):
        details = details_raw
    message_value = record.get("incompatibility_message")
    message = str(message_value).strip() if isinstance(message_value, str | int | float) else ""
    return build_compatibility_info(reason, message, details, override_flag)


def ensure_record_is_compatible(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    record: JSONDict | None,
) -> None:
    if not record:
        return
    compatibility = compatibility_from_record(record)
    if compatibility.reason and (not compatibility.is_overridden):
        if compatibility.reason in self.policy.hardware_incompatible_reasons:
            user_enabled = coerce_bool_with_recovery(
                record,
                "user_enabled_once",
                logger=get_logger(LOGGER_NAME),
                operation="plugins.manager.compatibility.coerce_compatibility_bool",
                default=False,
                recover_message=(
                    "Failed to parse boolean flag from compatibility record (non-critical)."
                ),
            )
            if user_enabled or record.get("state") == ORCH_STATE_DISABLED:
                return
        raise PluginIncompatibleError(plugin_name, compatibility)


async def ensure_system_capabilities(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    action_description: str,
    action_key: str | None = None,
) -> JSONDict:
    await self.require_ready()
    plugin_record = await require_plugin_record(self.dependencies.databases.plugins, plugin_name)
    report = await build_system_capability_report(
        self,
        plugin_name,
        plugin_record.get("required_system_capabilities"),
        plugin_record,
        self.dependencies.infrastructure.hardware_helpers.get_gpu_info,
    )
    if report["status"] != "supported" and (
        action_key is None
        or not (blocking := report.get("blocking_actions"))
        or (isinstance(blocking, list) and action_key in {str(entry) for entry in blocking})
    ):
        display_name = await self.get_plugin_display_name(plugin_name)
        messages_value = report.get("messages")
        messages = messages_value if isinstance(messages_value, list) else []
        message = str(messages[0]) if messages else "Host hardware requirements are not satisfied."
        raise PluginCapabilityError(
            plugin_name,
            "SYSTEM_CAPABILITIES",
            f"{action_description} for '{display_name}' is blocked. {message}",
        )
    return report


async def is_plugin_compatible(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[bool, str | None, str]:
    plugin_info = await self.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if not plugin_info:
        return (False, "Plugin not found.", self.state.configuration.core_version)
    compatibility = compatibility_from_record(plugin_info)
    should_block, _ = should_block_for_incompatibility(
        compatibility,
        plugin_info,
        self.policy.hardware_incompatible_reasons,
    )
    if should_block:
        core_compat = plugin_info.get("core_compat", ">=1.0.0")
        core_compat_value = str(core_compat) if not isinstance(core_compat, str) else core_compat
        return (False, compatibility.message, core_compat_value)
    core_compat = plugin_info.get("core_compat", ">=1.0.0")
    core_compat_value = str(core_compat) if not isinstance(core_compat, str) else core_compat
    return (True, None, core_compat_value)


async def ensure_plugin_compatible(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
    plugin_info = await require_plugin_record(self.dependencies.databases.plugins, plugin_name)
    ensure_record_is_compatible(self, plugin_name, plugin_info)
