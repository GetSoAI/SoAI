"""SoAI - Compatibility override toggling for plugins [backend/plugins/loader/override.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.events.completion_waiting import publication_completion_deadline
from core.plugins.name_validation import require_plugin_name
from core.runtime.request_context import create_system_context
from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_STOPPED,
)
from core.types.json import JSONDict
from plugins.identity import normalize_plugin_lookup_key
from plugins.manager.compatibility import compatibility_from_record
from plugins.manifest.reader import read_plugin_manifest_from_disk
from plugins.package_audit import audit_plugin_package
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.compatibility import build_compatibility_info
from plugins.state.manifest_compatibility import check_plugin_manifest_compatibility

__all__ = ("set_incompatibility_override",)

OPERATION = "plugins.loader.override.package_audit"
PLUGIN_OVERRIDE_SOURCE_AUDIT_EXCEPTIONS = (
    AttributeError,
    KeyError,
    NotFoundError,
    OSError,
    RuntimeError,
    SecurityError,
    StateError,
    SyntaxError,
    TypeError,
    ValidationError,
    ValueError,
)


async def _resolve_override_record(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[str, JSONDict]:
    requested_name = require_plugin_name(plugin_name)
    normalized_name = manager.normalize_plugin_name(requested_name)
    lookup_name = normalized_name or normalize_plugin_lookup_key(requested_name)
    if lookup_name is None:
        raise ValidationError(f"Plugin '{requested_name}' not found.")
    record = await manager.dependencies.databases.plugins.get_plugin_by_name(lookup_name)
    if not record:
        raise ValidationError(f"Plugin '{requested_name}' does not exist.")
    record_name = record.get("plugin_name")
    if not isinstance(record_name, str) or not record_name.strip():
        raise ValidationError(f"Plugin '{requested_name}' has invalid catalog identity.")
    return record_name.strip(), record


async def set_incompatibility_override(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    override: bool,
) -> CompatibilityInfo:
    manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    target_name, record = await _resolve_override_record(manager, plugin_name)
    compatibility = compatibility_from_record(record)
    if not compatibility.reason:
        if override:
            raise ValidationError(
                f"Plugin '{target_name}' is already compatible; no override required.",
            )
        await manager.dependencies.databases.plugins.set_incompatibility_override(
            target_name,
            False,
        )
        return compatibility
    if not compatibility.can_override:
        raise ValidationError(f"Plugin '{target_name}' incompatibility cannot be overridden.")
    if override == compatibility.is_overridden:
        return compatibility
    await manager.dependencies.databases.plugins.set_incompatibility_override(
        target_name,
        override,
    )
    base_info = build_compatibility_info(
        compatibility.reason,
        compatibility.message,
        compatibility.details,
        override,
    )
    context = create_system_context("set_incompatibility_override")
    publication_deadline = publication_completion_deadline()
    if override:
        receipt = await manager.transition_plugin_manager_state(
            target_name,
            PLUGIN_STATE_STOPPED,
            "User enabled incompatibility override.",
            context,
        )
        if receipt is not None:
            await receipt.wait_for_completion(publication_deadline)
        return base_info
    try:
        package_audit = await audit_plugin_package(manager, target_name)
        manifest = read_plugin_manifest_from_disk(
            manager,
            target_name,
            package_audit=package_audit,
        )
    except PLUGIN_OVERRIDE_SOURCE_AUDIT_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            manager.logger,
            coerced,
            message="Plugin source audit failed after disabling incompatibility override.",
            operation=OPERATION,
            details={"plugin_name": target_name},
        )
        message = (
            f"Plugin '{target_name}' failed source audit after disabling override: {exception}"
        )
        error_payload = ErrorPublicPayload(
            code="plugin_error",
            message=message,
            details={"exception": str(exception)},
        ).to_dict()
        info = build_compatibility_info(
            IncompatibilityReason.BROKEN_PLUGIN,
            message,
            {"error": error_payload},
            False,
        )
        await manager.dependencies.databases.plugins.set_incompatibility(
            target_name,
            info,
        )
        receipt = await manager.transition_plugin_manager_state(
            target_name,
            PLUGIN_STATE_INCOMPATIBLE,
            message,
            context,
        )
        if receipt is not None:
            await receipt.wait_for_completion(publication_deadline)
        return info
    refreshed = await check_plugin_manifest_compatibility(
        target_name,
        manifest,
        manager.state.configuration.core_version,
        manager.dependencies.infrastructure.hardware_helpers.get_gpu_info,
        record,
    )
    if refreshed.reason:
        updated = build_compatibility_info(
            refreshed.reason,
            refreshed.message,
            refreshed.details,
            False,
        )
        target_state = (
            ORCH_STATE_DISABLED
            if refreshed.reason in manager.policy.hardware_incompatible_reasons
            else PLUGIN_STATE_INCOMPATIBLE
        )
        await manager.dependencies.databases.plugins.set_incompatibility(
            target_name,
            updated,
            state=target_state,
        )
        receipt = await manager.transition_plugin_manager_state(
            target_name,
            target_state,
            updated.message or "Plugin marked as incompatible.",
            context,
        )
        if receipt is not None:
            await receipt.wait_for_completion(publication_deadline)
        return updated
    await manager.dependencies.databases.plugins.clear_incompatibility(
        target_name,
    )
    receipt = await manager.transition_plugin_manager_state(
        target_name,
        PLUGIN_STATE_STOPPED,
        "Plugin compatibility verified after disabling override.",
        context,
    )
    if receipt is not None:
        await receipt.wait_for_completion(publication_deadline)
    return build_compatibility_info(None, "", {}, False)
