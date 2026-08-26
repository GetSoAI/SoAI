"""SoAI - Plugin clone planning and validation [backend/plugins/clone/clone_planning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_path_exists
from core.plugins.clone_configuration import validate_clone_configuration_inputs
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.plugins.runtime_services import PluginPathResolver
from core.types.json import JSONDict
from plugins.clone.clone_plan import ClonePlan
from plugins.clone_paths import resolve_default_models_dir
from plugins.identity import (
    normalize_plugin_target_name,
    require_plugin_identifier,
)
from plugins.manager.capability_support import (
    supports_plugin_capability_from_instance,
    supports_plugin_capability_from_record,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.protocols_internal.task_progress.internal_protocols import (
    TaskProgressSenderProtocol,
)

__all__ = ("resolve_clone_plan",)


async def resolve_clone_plan(
    plugin_manager: PluginManagerRuntimeProtocol,
    *,
    source_plugin_name: str,
    target_name: str | None,
    clone_models: bool,
    field_overrides: JSONDict | None,
    source_config: JSONDict,
    progress_callback: TaskProgressSenderProtocol,
    reservation_task_id: str | None = None,
) -> ClonePlan:
    await progress_callback(1, "Validating source plugin...")
    source_display_name = await plugin_manager.get_plugin_display_name(source_plugin_name)
    source_plugin_record = await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
        source_plugin_name,
    )
    if not source_plugin_record:
        raise ValidationError(
            f"Source plugin '{source_display_name}' does not exist in the database.",
        )
    source_instance = await plugin_manager.get_plugin_instance(source_plugin_name)
    if source_instance:
        supports_cloning = supports_plugin_capability_from_instance(
            source_instance,
            "SUPPORTS_CLONING",
        )
    else:
        supports_cloning = supports_plugin_capability_from_record(
            source_plugin_record,
            "SUPPORTS_CLONING",
        )
    if not supports_cloning:
        raise ValidationError(f"Plugin '{source_display_name}' does not support cloning.")
    source_clonable_fields = source_instance.CLONABLE_FIELDS if source_instance is not None else ()
    if field_overrides and source_instance is None:
        raise ValidationError("Clone field overrides require an active source plugin instance.")
    clonable_fields = validate_clone_configuration_inputs(
        source_clonable_fields,
        field_overrides,
    )

    source_models_path: str | None = None
    source_models_path_exists = False
    if clone_models:
        models_override = source_config.get("MODELS_PATH_OVERRIDE")
        if isinstance(models_override, str) and models_override.strip():
            source_models_path = PluginPathResolver(
                source_plugin_name,
                plugin_manager.dependencies.core.config,
                plugin_manager.dependencies.core.files,
                source_config,
            ).models_directory()
        elif source_instance is not None:
            try:
                source_models_path = source_instance.get_models_directory()
            except RECOVERABLE_EXCEPTIONS as exception:
                raise StateError(
                    "Source plugin models directory is temporarily unavailable."
                ) from exception
        else:
            source_models_path = resolve_default_models_dir(
                plugin_manager,
                source_plugin_name,
            )
        if source_models_path:
            source_models_path_exists = await async_path_exists(source_models_path)

    await progress_callback(5, "Revalidating reserved clone target...")
    reserved_target_name = normalize_plugin_target_name(target_name)
    if reserved_target_name is None or not reservation_task_id:
        raise StateError("Clone planning requires durable target reservation ownership.")
    require_plugin_identifier(
        reserved_target_name,
        invalid_message=(
            f"Invalid target name '{reserved_target_name}'. Use alphanumeric characters, dashes, or underscores."
        ),
    )
    candidate_plugin_file = os.path.join(
        plugin_manager.paths.plugin_directory,
        f"{reserved_target_name}{PLUGIN_FILE_SUFFIX}",
    )
    if await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
        reserved_target_name,
    ):
        raise ValidationError(f"A plugin named '{reserved_target_name}' already exists.")
    reservation_owner = (
        await plugin_manager.dependencies.databases.plugins.clone_transactions.get_target_owner(
            reserved_target_name
        )
    )
    if reservation_owner != reservation_task_id:
        raise StateError("Clone target reservation ownership was lost.")
    if await async_path_exists(candidate_plugin_file):
        raise ValidationError(
            f"Plugin file '{reserved_target_name}{PLUGIN_FILE_SUFFIX}' already exists on disk."
        )
    computed_target_models_path: str | None = None
    if clone_models and source_models_path_exists:
        if source_models_path is None:
            raise ValidationError(
                "Cannot determine target models path: source models path is missing.",
            )
        models_parent_dir = os.path.dirname(source_models_path)
        if not models_parent_dir:
            raise ValidationError(
                f"Cannot determine target models path: source path '{source_models_path}' has no parent directory.",
            )
        computed_target_models_path = os.path.join(
            models_parent_dir,
            reserved_target_name,
        )
        if await async_path_exists(computed_target_models_path):
            raise ValidationError(
                f"Target models directory '{computed_target_models_path}' already exists."
            )
    await progress_callback(8, "Preparing clone plan...")
    return ClonePlan(
        source_plugin_name=source_plugin_name,
        source_display_name=source_display_name,
        target_plugin_name=reserved_target_name,
        target_plugin_file=candidate_plugin_file,
        source_models_path=source_models_path,
        source_models_path_exists=source_models_path_exists,
        target_models_path=computed_target_models_path,
        clone_models=clone_models,
        clonable_fields=clonable_fields,
    )
