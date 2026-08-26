"""SoAI - Orchestrator routing configuration updates and virtual model management [backend/orchestrator/lifecycle/routing_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import (
    EventPublicationReceipt,
    publication_completion_deadline,
)
from core.events.types_base import Event
from core.events.types_models_routing_commands import (
    GetRoutingConfigCommand,
    UpdateRoutingConfigCommand,
)
from core.events.types_models_routing_events import RoutingConfigChangedEvent
from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.orchestrator.routing_config import (
    ConstituentModelConfig,
    FailoverConfig,
    VirtualModelConfig,
)
from core.orchestrator.routing_config_builders import build_routing_config
from core.tasks.api_events import send_task_complete_event
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.epoch import epoch_ms
from orchestrator.lifecycle.state_access.internal_protocols import (
    RoutingConfigProviderProtocol,
)
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorLifecycleRoutingConfig",
    "OrchestratorLifecycleRoutingConfigDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.routing_config"
OPERATION_ORCHESTRATOR_APPLY_CORE_ROUTING_CONFIG_UPDATE = (
    "orchestrator.apply_core_routing_config_update"
)
OPERATION_ORCHESTRATOR_HANDLE_GET_ROUTING_CONFIG = "orchestrator.handle_get_routing_config"
OPERATION_ORCHESTRATOR_LIFECYCLE_ROUTING_CONFIG_HANDLE_COMMAND = (
    "orchestrator.lifecycle.routing_config.handle_command"
)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleRoutingConfigDependencies:
    orchestrator: OrchestratorDependencies
    routing_config_provider: RoutingConfigProviderProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleRoutingConfigDependencies",
            orchestrator=self.orchestrator,
            routing_config_provider=self.routing_config_provider,
            task_registry=self.task_registry,
        )


class OrchestratorLifecycleRoutingConfig:
    def __init__(self, deps: OrchestratorLifecycleRoutingConfigDependencies) -> None:
        self._deps = deps

    async def apply_core_routing_config_update(self, event: ConfigReloadedEvent) -> str | None:
        logger = get_logger(LOGGER_NAME)
        config_dict = event.config_dict
        if not isinstance(config_dict, dict):
            return "invalid configuration payload"
        models_section = config_dict.get("MODELS")
        routing_section = (
            models_section.get("ROUTING") if isinstance(models_section, dict) else None
        )
        if not isinstance(routing_section, dict):
            return None
        try:
            routing_section_json: JSONDict = {
                key: value for key, value in routing_section.items() if isinstance(key, str)
            }
            new_routing_config = build_routing_config(routing_section_json, logger)
            published_virtual_models: list[VirtualModelConfig] = list(
                new_routing_config.virtual_models,
            )
            published_failovers: list[FailoverConfig] = list(new_routing_config.failovers)
            receipt = EventPublicationReceipt.create(
                event_type=RoutingConfigChangedEvent.__name__,
                operation="orchestrator.apply_core_routing_config_update",
            )
            await self._deps.orchestrator.bus.publish(
                RoutingConfigChangedEvent(
                    virtual_models=published_virtual_models,
                    failovers=published_failovers,
                    routing_config=new_routing_config,
                ),
                wait_for_completion=receipt.completion_signal,
            )
            await receipt.wait_for_completion(publication_completion_deadline())
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to apply core routing configuration update.",
                operation=OPERATION_ORCHESTRATOR_APPLY_CORE_ROUTING_CONFIG_UPDATE,
                details={"source": event.source, "path": event.path},
                level="warning",
            )
            return str(exception)
        return None

    async def handle_get_routing_config(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(event, GetRoutingConfigCommand):
            return
        reply_channel = event.reply_channel
        try:
            current_config = self._deps.routing_config_provider.routing_config
            response_event = RoutingConfigChangedEvent(
                virtual_models=list(current_config.virtual_models),
                failovers=list(current_config.failovers),
                routing_config=current_config,
            )
            if not put_nowait_with_overwrite(
                reply_channel,
                response_event,
                overwrite_attempts=2,
            ).delivered:
                logger.error(
                    "Failed to deliver routing config response: reply channel unavailable.",
                )
                await send_error_event_and_finalize(
                    reply_channel,
                    "Failed to deliver routing config response.",
                    ErrorType.SERVER_ERROR,
                    registry=self._deps.task_registry,
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to handle GetRoutingConfigCommand",
                operation=OPERATION_ORCHESTRATOR_HANDLE_GET_ROUTING_CONFIG,
            )
            await send_error_event_and_finalize(
                reply_channel,
                f"Failed to retrieve routing config: {exception}",
                ErrorType.SERVER_ERROR,
                registry=self._deps.task_registry,
            )

    async def handle_update_routing_config(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(event, UpdateRoutingConfigCommand):
            return
        reply_channel = event.reply_channel
        action = event.action
        entity_type = event.entity_type
        data = event.data
        try:
            if entity_type != "virtual_model":
                raise ValidationError(
                    f"Unsupported entity type for routing config update: {entity_type}",
                )
            name_value = data.get("name")
            if not isinstance(name_value, str):
                raise ValidationError("Missing or invalid 'name' field in routing config update")
            if action == "add":
                strategy_value = data.get("strategy")
                if not isinstance(strategy_value, str):
                    raise ValidationError(
                        "Missing or invalid 'strategy' field in routing config update",
                    )
                models_value = data.get("models", [])
                if not isinstance(models_value, list):
                    raise ValidationError("Invalid 'models' field in routing config update")
                constituent_models: list[ConstituentModelConfig] = []
                for model_entry in models_value:
                    if not isinstance(model_entry, dict):
                        continue
                    uid = model_entry.get("universal_id")
                    if not isinstance(uid, str):
                        continue
                    params = model_entry.get("parameters", {})
                    constituent_models.append(
                        ConstituentModelConfig(
                            universal_id=uid,
                            parameters=params if isinstance(params, dict) else {},
                        ),
                    )
                virtual_model_config = VirtualModelConfig(
                    name=name_value,
                    strategy=strategy_value,
                    models=constituent_models,
                    created_at_ms=epoch_ms(),
                    last_modified_at_ms=epoch_ms(),
                )
                await self._deps.orchestrator.model_virtual_model_service.virtual_model_add(
                    virtual_model_config,
                )
                message = f"Virtual model '{virtual_model_config.name}' created successfully."
            elif action == "update":
                await self._deps.orchestrator.model_virtual_model_service.virtual_model_update(
                    name_value,
                    {
                        field_key: field_value
                        for field_key, field_value in data.items()
                        if field_key != "name"
                    },
                )
                message = f"Virtual model '{name_value}' updated successfully."
            elif action == "set_enabled":
                enabled_value = data.get("enabled")
                if not isinstance(enabled_value, bool):
                    raise ValidationError(
                        "Missing or invalid 'enabled' field in routing config update",
                    )
                await self._deps.orchestrator.model_virtual_model_service.virtual_model_set_enabled(
                    name_value,
                    enabled_value,
                )
                message = (
                    f"Virtual model '{name_value}' "
                    f"{'enabled' if enabled_value else 'disabled'} successfully."
                )
            elif action == "remove":
                deleted = (
                    await self._deps.orchestrator.model_virtual_model_service.virtual_model_delete(
                        name_value,
                    )
                )
                if not deleted:
                    raise ValidationError(f"Virtual model '{name_value}' not found.")
                message = f"Virtual model '{name_value}' deleted successfully."
            else:
                raise ValidationError(f"Unsupported action: {action}")
            await send_task_complete_event(
                reply_channel,
                message,
                registry=self._deps.task_registry,
            )
        except (ValueError, KeyError, ValidationError) as exception:
            await send_error_event_and_finalize(
                reply_channel,
                str(exception),
                ErrorType.INVALID_REQUEST,
                registry=self._deps.task_registry,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to update routing config.",
                operation=OPERATION_ORCHESTRATOR_LIFECYCLE_ROUTING_CONFIG_HANDLE_COMMAND,
                details={"action": action},
                level="warning",
            )
            await send_error_event_and_finalize(
                reply_channel,
                f"Failed to update routing config: {exception}",
                ErrorType.SERVER_ERROR,
                registry=self._deps.task_registry,
            )
