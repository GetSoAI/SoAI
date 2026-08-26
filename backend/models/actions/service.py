"""SoAI - Model CRUD operations with aliases and tracking [backend/models/actions/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_models_model_commands import ModelDeleteCommand
from core.events.types_plugins import PurgeModelsForPluginCommand
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.state.state_names import ORCH_STATE_DISABLED
from core.tasks.cancellation_id import (
    ensure_command_cancellation_id,
    require_command_cancellation_id,
)
from core.validation.boolean_coercion import coerce_bool_with_default
from models.actions.delete_workflows import (
    process_model_delete_command,
    process_model_purge_for_plugin_command,
)
from models.actions.dependencies import ModelActionsServiceDependencies
from models.actions.openai_capability_overrides import (
    reset_model_openai_capability_overrides,
    update_model_openai_capability_override,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ModelActionsService",)

LOGGER_NAME = "SoAI.models.actions.service"


class ModelActionsService:
    def __init__(self, deps: ModelActionsServiceDependencies) -> None:
        self._deps = deps

    async def model_validate_and_get_context(self, universal_id: str) -> tuple[JSONDict, str]:
        if not (info := await self._deps.model_get_info(universal_id)):
            raise ValidationError(f"Model '{universal_id}' not found.")
        plugin_value = info.get("plugin")
        if not isinstance(plugin_value, str) or not plugin_value:
            raise ValidationError(f"Model '{universal_id}' is missing a valid plugin name.")
        plugin_name = plugin_value
        if plugin_name not in self._deps.installed_plugin_names_ref():
            raise ValidationError(
                f"Plugin '{plugin_name}' for model '{universal_id}' is not installed.",
            )
        if await self._deps.state_aggregator.get_plugin_status(plugin_name) == ORCH_STATE_DISABLED:
            raise ValidationError(f"Plugin '{plugin_name}' for model '{universal_id}' is disabled.")
        return (info, plugin_name)

    async def model_update_alias(
        self,
        universal_id: str,
        name: str | None,
        desc: str | None = None,
    ) -> None:
        _info, _ = await self.model_validate_and_get_context(universal_id)
        updates: JSONDict = {
            key: value
            for key, value in {"display_name": name, "description": desc}.items()
            if value is not None
        }
        if not updates:
            return
        async with self._deps.model_record_locks[universal_id]:
            if not await self._deps.database_models.update_model_alias(universal_id, updates):
                raise ValidationError(f"Failed to update alias for model '{universal_id}'.")
        await self._deps.mutation_effects.publish_catalog_changed()

    async def model_delete_alias(self, universal_id: str) -> None:
        info, _ = await self.model_validate_and_get_context(universal_id)
        if info.get("display_name") is not None or info.get("description") is not None:
            async with self._deps.model_record_locks[universal_id]:
                if not await self._deps.database_models.update_model_alias(
                    universal_id,
                    {"display_name": None, "description": None},
                ):
                    raise ValidationError(f"Failed to delete alias for model '{universal_id}'.")
            await self._deps.mutation_effects.publish_catalog_changed()

    async def model_update_enabled(self, universal_id: str, enabled: bool) -> None:
        normalized_universal_id = str(universal_id or "").strip()
        if not normalized_universal_id:
            raise ValidationError("universal_id is required.")
        async with self._deps.model_record_locks[normalized_universal_id]:
            current_info = await self._deps.database_models.get_model_info(normalized_universal_id)
            if not current_info:
                raise ValidationError(f"Model '{normalized_universal_id}' not found.")
            current_enabled = coerce_bool_with_default(
                current_info.get("is_enabled"),
                default=True,
                strict=True,
            )
            if current_enabled == bool(enabled):
                return
            updated = await self._deps.database_models.update_model_enabled(
                normalized_universal_id,
                bool(enabled),
            )
            if not updated:
                raise ValidationError(
                    f"Failed to update enabled status for model '{normalized_universal_id}'.",
                )
        await self._deps.mutation_effects.publish_catalog_changed()

    async def model_update_openai_capability_override(
        self,
        universal_id: str,
        category: str,
        token: str,
        enabled: bool,
    ) -> None:
        _info, plugin_name = await self.model_validate_and_get_context(universal_id)
        await update_model_openai_capability_override(
            self._deps,
            universal_id=universal_id,
            plugin_name=plugin_name,
            category=category,
            token=token,
            enabled=enabled,
        )
        await self._deps.mutation_effects.publish_catalog_changed()

    async def model_reset_openai_capability_overrides(self, universal_id: str) -> None:
        _info, _plugin_name = await self.model_validate_and_get_context(universal_id)
        await reset_model_openai_capability_overrides(self._deps, universal_id=universal_id)
        await self._deps.mutation_effects.publish_catalog_changed()

    async def model_purge_for_plugin(self, plugin_name: str) -> bool:
        return await self._deps.model_database_purge_service.purge_models_for_plugin(
            plugin_name,
            self._deps.plugin_manager.lifecycle,
        )

    async def model_process_delete_command_async(self, command: ModelDeleteCommand) -> None:
        await process_model_delete_command(self._deps, command)

    async def modelhandle_delete_command(self, command: ModelDeleteCommand) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = self._deps.spawn_tracked_task(
            self.model_process_delete_command_async(command),
            name=f"model-manager-delete-{command.universal_id}",
            cancellation_binder=self._deps.cancellation_binder,
            cancellation_id=require_command_cancellation_id(command),
            owner="model_delete",
            logger=logger,
            metadata={"universal_id": command.universal_id},
            finalizer_tracker=self._deps.finalizer_tracker,
        )

    async def model_process_purge_for_plugin_async(
        self,
        command: PurgeModelsForPluginCommand,
    ) -> None:
        await process_model_purge_for_plugin_command(self._deps, command)

    async def model_handle_purge_for_plugin_command(
        self,
        command: PurgeModelsForPluginCommand,
    ) -> None:
        logger = get_logger(LOGGER_NAME)

        def _default_cancellation_id() -> str:
            return create_system_id(
                subsystem="model_purge",
                owner=command.plugin_name,
                include_random_suffix=True,
            )

        _ = self._deps.spawn_tracked_task(
            self.model_process_purge_for_plugin_async(command),
            name=f"model-manager-purge-{command.plugin_name}",
            cancellation_binder=self._deps.cancellation_binder,
            cancellation_id=ensure_command_cancellation_id(
                command,
                default_factory=_default_cancellation_id,
            ),
            owner="model_purge",
            logger=logger,
            metadata={"plugin": command.plugin_name},
            finalizer_tracker=self._deps.finalizer_tracker,
        )
