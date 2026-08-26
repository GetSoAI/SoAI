"""SoAI - Model manager event handlers and side effects [backend/models/manager/coordinator/event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_model_commands import (
    DeleteModelAliasCommand,
    DeleteModelParametersCommand,
    ModelDeleteCommand,
    ResetModelOpenAICapabilityOverridesCommand,
    TriggerModelDiscoveryCommand,
    UpdateModelAliasCommand,
    UpdateModelEnabledCommand,
    UpdateModelOpenAICapabilityOverrideCommand,
    UpdateModelParametersCommand,
)
from core.events.types_models_model_events import ModelParametersRequireReloadEvent
from core.events.types_plugins import PurgeModelsForPluginCommand
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.api_events import send_task_complete_event
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_id import ensure_command_cancellation_id
from core.tasks.failure_events import send_error_event_and_finalize
from models.manager.coordinator.dependencies import ModelManagerDependencies

__all__ = ("ModelManagerEventHandlers",)

LOGGER_NAME = "SoAI.models.manager.event_handlers"
OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_ALIAS = "models.manager.coordinator.command.alias"
OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_ENABLED = "models.manager.coordinator.command.enabled"
OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_OPENAI_CAPABILITY_OVERRIDE = (
    "models.manager.coordinator.command.openai_capability_override"
)
OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_PARAMETERS = (
    "models.manager.coordinator.command.parameters"
)


class ModelManagerEventHandlers:
    def __init__(
        self,
        *,
        deps: ModelManagerDependencies,
        background_tasks: ManagedTaskGroup,
        shutdown_event: asyncio.Event,
    ) -> None:
        self._deps = deps
        self._background_tasks = background_tasks
        self._shutdown_event = shutdown_event

    async def handle_delete_model_command(self, command: Event) -> None:
        if not isinstance(command, ModelDeleteCommand):
            return
        await self._deps.model_actions_service.modelhandle_delete_command(command)

    async def handle_purge_models_for_plugin_command(self, command: Event) -> None:
        if not isinstance(command, PurgeModelsForPluginCommand):
            return
        await self._deps.model_actions_service.model_handle_purge_for_plugin_command(command)

    async def handle_discover_models_command(self, command: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(command, TriggerModelDiscoveryCommand):
            return
        if self._shutdown_event.is_set():
            return
        logger.info(
            "Received command to discover models for: %s",
            command.plugins_to_scan or "all",
        )

        def _default_cancellation_id() -> str:
            plugins_str = (
                "-".join(sorted(command.plugins_to_scan)) if command.plugins_to_scan else "all"
            )
            return create_system_id(
                subsystem="model_discovery",
                owner=plugins_str,
                include_random_suffix=True,
            )

        if command.wait_for_completion:
            await self._deps.model_discovery_service.model_discover_all(
                plugins_to_scan=command.plugins_to_scan,
                wait_for_completion=True,
            )
            return
        task = spawn_tracked_task(
            self._deps.model_discovery_service.model_discover_all(
                plugins_to_scan=command.plugins_to_scan,
            ),
            name="model-coordinator-discovery",
            cancellation_id=ensure_command_cancellation_id(
                command,
                default_factory=_default_cancellation_id,
            ),
            owner="model_discovery",
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            logger=logger,
            metadata={"plugins": list(command.plugins_to_scan or [])},
        )
        _ = self._background_tasks.track(task)

    async def handle_parameter_command(self, command: Event) -> None:
        if not isinstance(command, UpdateModelParametersCommand | DeleteModelParametersCommand):
            return
        try:
            if isinstance(command, UpdateModelParametersCommand):
                await self._deps.model_parameter_mutations.enqueue_update(
                    command.universal_id,
                    command.parameters,
                    command.reply_channel,
                )
            else:
                await self._deps.model_parameter_mutations.enqueue_delete(
                    command.universal_id,
                    command.keys,
                    command.reply_channel,
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Model parameter command failed.",
                operation=OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_PARAMETERS,
            )
            await send_error_event_and_finalize(
                command.reply_channel,
                str(exception),
                ErrorType.INVALID_REQUEST,
                registry=self._deps.task_registry,
            )

    async def handle_alias_command(self, command: Event) -> None:
        if not isinstance(command, UpdateModelAliasCommand | DeleteModelAliasCommand):
            return
        try:
            if isinstance(command, UpdateModelAliasCommand):
                await self._deps.model_actions_service.model_update_alias(
                    command.universal_id,
                    command.display_name,
                    command.description,
                )
            else:
                await self._deps.model_actions_service.model_delete_alias(command.universal_id)
            action = "updated" if isinstance(command, UpdateModelAliasCommand) else "deleted"
            await send_task_complete_event(
                command.reply_channel,
                f"Model alias {action} successfully.",
                registry=self._deps.task_registry,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Model alias command failed.",
                operation=OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_ALIAS,
            )
            await send_error_event_and_finalize(
                command.reply_channel,
                str(exception),
                ErrorType.INVALID_REQUEST,
                registry=self._deps.task_registry,
            )

    async def handle_enabled_command(self, command: Event) -> None:
        if not isinstance(command, UpdateModelEnabledCommand):
            return
        try:
            await self._deps.model_actions_service.model_update_enabled(
                command.universal_id,
                command.enabled,
            )
            await send_task_complete_event(
                command.reply_channel,
                "Model enabled status updated successfully.",
                registry=self._deps.task_registry,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Model enabled status command failed.",
                operation=OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_ENABLED,
            )
            await send_error_event_and_finalize(
                command.reply_channel,
                str(exception),
                ErrorType.INVALID_REQUEST,
                registry=self._deps.task_registry,
            )

    async def handle_openai_capabilities_override_command(self, command: Event) -> None:
        if not isinstance(
            command,
            UpdateModelOpenAICapabilityOverrideCommand | ResetModelOpenAICapabilityOverridesCommand,
        ):
            return
        try:
            if isinstance(command, ResetModelOpenAICapabilityOverridesCommand):
                await self._deps.model_actions_service.model_reset_openai_capability_overrides(
                    command.universal_id,
                )
            else:
                await self._deps.model_actions_service.model_update_openai_capability_override(
                    command.universal_id,
                    command.category,
                    command.token,
                    command.enabled,
                )
            action = (
                "reset"
                if isinstance(command, ResetModelOpenAICapabilityOverridesCommand)
                else "updated"
            )
            await send_task_complete_event(
                command.reply_channel,
                f"Model OpenAI capabilities {action} successfully.",
                registry=self._deps.task_registry,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Model OpenAI capability override command failed.",
                operation=OPERATION_MODELS_MANAGER_COORDINATOR_COMMAND_OPENAI_CAPABILITY_OVERRIDE,
            )
            await send_error_event_and_finalize(
                command.reply_channel,
                str(exception),
                ErrorType.INVALID_REQUEST,
                registry=self._deps.task_registry,
            )

    async def handle_parameters_require_reload(self, event: Event) -> None:
        if not isinstance(event, ModelParametersRequireReloadEvent):
            return
        if self._shutdown_event.is_set():
            return
        await self._deps.model_parameter_cache.invalidate(event.universal_id)
        await self._deps.model_information_service.model_invalidate_list_caches()
