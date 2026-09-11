"""SoAI - Plugin upload validation and normalization helpers [backend/plugins/actions/upload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.filesystem.async_queries import async_path_exists
from core.plugins.errors import PluginIncompatibleError
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
)
from plugins.context_ids import resolve_task_id_from_context
from plugins.fs_permissions import ensure_correct_permissions
from plugins.internal_protocols import SendCompletionWithTaskProtocol
from plugins.loader.incompatibility import handle_plugin_compatibility_failure
from plugins.loader.preflight import perform_plugin_preflight_checks
from plugins.manager.compatibility import compatibility_from_record
from plugins.manager.initial_state import get_initial_plugin_manager_state
from plugins.manager.instance_loading import load_plugin_instance
from plugins.manifest.reader import read_plugin_manifest_from_disk
from plugins.path_safety import normalize_plugin_filename

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.events.types_plugins import UploadPluginCommand
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "load_and_validate_uploaded_plugin",
    "normalize_upload_target",
    "reject_upload_preflight_if_needed",
    "resolve_upload_failure_code",
    "resolve_upload_failure_message",
    "resolve_upload_task_id",
    "safe_delete_upload_environment",
    "safe_remove_upload_file",
    "UploadedPluginDisposition",
    "UploadedPluginOutcome",
    "validate_loaded_plugin_compatibility",
    "validate_upload_destination_available",
)

OPERATION = "plugin_flow.process_upload_plugin_async"


class UploadedPluginDisposition(StrEnum):
    LOADED = "loaded"
    RETAINED_INCOMPATIBLE = "retained_incompatible"


@dataclass(frozen=True, slots=True)
class UploadedPluginOutcome:
    disposition: UploadedPluginDisposition
    requires_backend_installation: bool


def resolve_upload_task_id(command: UploadPluginCommand) -> str | None:
    return resolve_task_id_from_context(command.context)


def normalize_upload_target(
    manager: PluginManagerRuntimeProtocol,
    original_filename: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not original_filename or not original_filename.strip():
        return None, None, "Plugin upload missing required filename."
    try:
        plugin_name, final_path = normalize_plugin_filename(manager, original_filename)
        return plugin_name, final_path, None
    except ValidationError as exception:
        return None, None, str(exception)


async def reject_upload_preflight_if_needed(
    *,
    manager: PluginManagerRuntimeProtocol,
    logger: LoggerProtocol,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str,
    registry: TaskRegistryProtocol,
    original_filename: str | None,
    normalize_error: str | None,
    send_completion_with_task: SendCompletionWithTaskProtocol,
) -> bool:
    if not manager.state.configuration.uploads_enabled:
        logger.warning(
            "Plugin upload rejected: uploads are disabled in configuration (file='%s').",
            original_filename,
        )
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message="Plugin uploads are disabled by the administrator.",
            error_code=403,
            task_registry=registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
        return True
    if normalize_error:
        logger.warning(
            "Blocked upload of plugin '%s': %s",
            original_filename,
            normalize_error,
        )
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message=normalize_error,
            error_code=400,
            task_registry=registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
        return True
    return False


async def validate_upload_destination_available(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    final_path: str,
) -> None:
    existing_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if existing_record is not None:
        raise ValidationError(f"A plugin named '{plugin_name}' already exists in the database.")
    if await async_path_exists(final_path):
        raise ValidationError(
            f"Plugin file '{plugin_name}{PLUGIN_FILE_SUFFIX}' already exists on disk. Please delete it first.",
        )


async def safe_remove_upload_file(final_path: str | None, *, logger: LoggerProtocol) -> None:
    if not final_path:
        return
    removed = await async_remove_if_exists(final_path, logger=logger, log_level=logging.ERROR)
    if removed:
        logger.info("Removed partially uploaded plugin file: %s", final_path)


async def safe_delete_upload_environment(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str | None,
    *,
    logger: LoggerProtocol,
) -> None:
    if not plugin_name:
        return
    try:
        await manager.worker_controller.delete_plugin_environment(plugin_name)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to delete plugin environment during upload cleanup.",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="warning",
        )


async def validate_loaded_plugin_compatibility(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if not plugin_record:
        raise StateError("Plugin upload failed: plugin record is missing after load.")
    plugin_state_value = plugin_record.get("state", PLUGIN_STATE_NOT_DETECTED)
    if plugin_state_value in {PLUGIN_STATE_INSTALL_ERROR, PLUGIN_STATE_LOAD_ERROR}:
        raise ValidationError(
            f"Plugin upload failed: plugin entered error state '{plugin_state_value}'.",
        )
    compatibility_info = compatibility_from_record(plugin_record)
    if compatibility_info.reason and (not compatibility_info.is_overridden):
        raise PluginIncompatibleError(plugin_name, compatibility_info)
    instance = await manager.get_plugin_instance(plugin_name)
    return bool(
        instance
        and await get_initial_plugin_manager_state(instance) == PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    )


def resolve_upload_failure_code(exception: BaseException) -> int:
    if isinstance(exception, PluginIncompatibleError):
        return 409
    if isinstance(exception, SecurityError):
        return 400
    if isinstance(exception, ValueError | ValidationError):
        return 400
    return 500


def resolve_upload_failure_message(exception: BaseException) -> str:
    if isinstance(exception, ValidationError):
        return str(exception)
    return project_public_exception(exception).message


async def load_and_validate_uploaded_plugin(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    package_audit: PluginPackageAudit,
) -> UploadedPluginOutcome:
    await ensure_correct_permissions(package_audit.archive_path)
    manifest = await asyncio.to_thread(
        read_plugin_manifest_from_disk,
        manager,
        plugin_name,
        package_audit=package_audit,
    )
    try:
        preflight_result = await perform_plugin_preflight_checks(
            manager,
            plugin_name,
            package_audit=package_audit,
            manifest=manifest,
        )
    except PluginIncompatibleError as exception:
        compatibility = exception.compatibility
        incompatible_plugin_class_name = exception.plugin_class_name
    else:
        compatibility = preflight_result.compatibility
        if not compatibility.reason or compatibility.is_overridden:
            await load_plugin_instance(
                manager,
                plugin_name,
                force_reload=True,
                already_serialized=True,
                preflight_result=preflight_result,
            )
            return UploadedPluginOutcome(
                disposition=UploadedPluginDisposition.LOADED,
                requires_backend_installation=await validate_loaded_plugin_compatibility(
                    manager,
                    plugin_name,
                ),
            )
        incompatible_plugin_class_name = None
    await handle_plugin_compatibility_failure(
        manager,
        plugin_name,
        compatibility,
        plugin_class_name=incompatible_plugin_class_name,
        plugin_data_override=manifest,
        package_audit=package_audit,
    )
    return UploadedPluginOutcome(
        disposition=UploadedPluginDisposition.RETAINED_INCOMPATIBLE,
        requires_backend_installation=False,
    )
