"""SoAI - Application runtime configuration reload handling [backend/app/runtime_config_reload_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.runtime_config_reload import (
    append_reload_error,
    assess_routing_only_reload,
    build_rate_limit_configuration_from_dict,
)
from core.config.protocols import CoreConfigReloadCoordinatorProtocol
from core.config.reload_coordinator import ReloadRejectionReason
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.subscriptions import publish_config_apply_event
from core.events.types_base import Event
from core.events.types_system import ConfigReloadedEvent
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from features.api.lifecycle.rate_limiting_config import apply_rate_limiting

if TYPE_CHECKING:
    from app.runtime_dependencies import ApplicationRuntimeCoordinatorDependencies
    from core.config.reload_coordinator import CoreConfigReloadClassification
    from core.orchestrator.protocols_lifecycle import (
        CoreRoutingConfigApplicatorProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ApplicationRuntimeConfigReloadHandler",
    "ApplicationRuntimeConfigReloadHandlerDependencies",
)

OPERATION_APPLICATION_RUNTIME_APPLY_RATE_LIMITING_RELOAD = (
    "application_runtime.apply_rate_limiting_reload"
)
OPERATION_APPLICATION_RUNTIME_APPLY_ROUTING_CONFIG_VIA_ORCHESTRATOR = (
    "application_runtime.apply_routing_config_via_orchestrator"
)
OPERATION_APPLICATION_RUNTIME_APPLY_RUNTIME_FLAGS_RELOAD = (
    "application_runtime.apply_runtime_flags_reload"
)


@dataclass(frozen=True, slots=True)
class ApplicationRuntimeConfigReloadHandlerDependencies:
    coordinator_dependencies: ApplicationRuntimeCoordinatorDependencies
    reload_coordinator: CoreConfigReloadCoordinatorProtocol
    startup_http_client_limits: dict[str, JSONValue] | None
    startup_http_client_timeouts: dict[str, JSONValue] | None
    require_restart: Callable[[str, str], Awaitable[None]]
    core_routing_applicator: CoreRoutingConfigApplicatorProtocol | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationRuntimeConfigReloadHandlerDependencies",
            coordinator_dependencies=self.coordinator_dependencies,
            reload_coordinator=self.reload_coordinator,
            require_restart=self.require_restart,
        )


class ApplicationRuntimeConfigReloadHandler:
    def __init__(self, deps: ApplicationRuntimeConfigReloadHandlerDependencies) -> None:
        self.deps = deps

    def apply_rate_limiting_reload(self, config_dict: JSONDict) -> str | None:
        runtime_state = self.deps.coordinator_dependencies.runtime_state
        fastapi_app = runtime_state.fastapi_app
        request_rate_limiter = runtime_state.request_rate_limiter
        if not isinstance(fastapi_app, FastAPI):
            return "FastAPI app not available for rate limiting reload."
        if not isinstance(request_rate_limiter, MovingWindowRateLimiter):
            return "Rate limiter not available for rate limiting reload."
        try:
            rate_limit_config = build_rate_limit_configuration_from_dict(config_dict)
            apply_rate_limiting(
                fastapi_app,
                request_rate_limiter,
                rate_limit_config,
                already_initialized=True,
            )
            self.deps.coordinator_dependencies.logging.logger.info(
                "API rate limiting configuration reloaded successfully.",
            )
            return None
        except RECOVERABLE_EXCEPTIONS as exception:
            error_message = f"Failed to reload API rate limiting configuration: {exception}"
            log_exception(
                self.deps.coordinator_dependencies.logging.logger,
                exception,
                message=error_message,
                operation=OPERATION_APPLICATION_RUNTIME_APPLY_RATE_LIMITING_RELOAD,
            )
            return error_message

    async def apply_routing_config_via_orchestrator(self, event: ConfigReloadedEvent) -> str | None:
        applicator = self.deps.core_routing_applicator
        if applicator is None:
            return None
        try:
            return await applicator.apply_core_routing_config_update(event)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self.deps.coordinator_dependencies.logging.logger,
                exception,
                message="Routing config applicator raised an unexpected error.",
                operation=OPERATION_APPLICATION_RUNTIME_APPLY_ROUTING_CONFIG_VIA_ORCHESTRATOR,
                level="warning",
            )
            return str(exception)

    async def apply_runtime_flags_reload(
        self,
        classification: CoreConfigReloadClassification,
    ) -> str | None:
        if (
            "SYSTEM.RUNTIME" not in classification.changed_keys
            and "SYSTEM.SECURITY" not in classification.changed_keys
        ):
            return None
        try:
            runtime_flags = self.deps.coordinator_dependencies.runtime_flags
            runtime_flags.update_runtime_policy(
                host_system_actions_disabled=_read_bool_path(
                    classification.config_dict,
                    ("SYSTEM", "RUNTIME", "HOST_SYSTEM_ACTIONS_DISABLED"),
                    default=runtime_flags.host_system_actions_disabled,
                ),
                hardware_mutation_disabled=_read_bool_path(
                    classification.config_dict,
                    ("SYSTEM", "RUNTIME", "HARDWARE_MUTATION_DISABLED"),
                    default=runtime_flags.hardware_mutation_disabled,
                ),
                offline_mode=_read_bool_path(
                    classification.config_dict,
                    ("SYSTEM", "RUNTIME", "STAY_OFFLINE"),
                    default=runtime_flags.offline_mode,
                ),
                block_private_network_egress=_read_bool_path(
                    classification.config_dict,
                    ("SYSTEM", "SECURITY", "BLOCK_PRIVATE_NETWORK_EGRESS"),
                    default=runtime_flags.block_private_network_egress,
                ),
                dns_validation_timeout_sec=_read_float_path(
                    classification.config_dict,
                    ("SYSTEM", "SECURITY", "DNS_VALIDATION_TIMEOUT_SEC"),
                    default=runtime_flags.dns_validation_timeout_sec,
                ),
                host_management_available=runtime_flags.host_management_available,
            )
            updater = self.deps.coordinator_dependencies.update_plugin_worker_runtime_flags
            if updater is not None:
                await updater(runtime_flags)
            return None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self.deps.coordinator_dependencies.logging.logger,
                exception,
                message="Failed to reload runtime network flags.",
                operation=OPERATION_APPLICATION_RUNTIME_APPLY_RUNTIME_FLAGS_RELOAD,
                level="warning",
            )
            return str(exception)

    async def handle_core_configuration_reload_event(self, event: Event) -> None:
        if not isinstance(event, ConfigReloadedEvent):
            return
        reload_result = self.deps.reload_coordinator.try_accept_reload(event)
        if reload_result.classification is None:
            if reload_result.rejection_reason == ReloadRejectionReason.INVALID_PAYLOAD:
                await self.publish_core_configuration_result(event, "invalid configuration payload")
            return
        classification = reload_result.classification
        self.deps.coordinator_dependencies.logging.logger.debug(
            "Core configuration reload received: revision=%s changed_keys=%s.",
            classification.revision,
            sorted(classification.changed_keys),
        )
        if not classification.requires_restart:
            await self._handle_live_reload(event, classification)
            return
        await self._handle_restart_reload(event, classification)

    async def _handle_live_reload(
        self,
        event: ConfigReloadedEvent,
        classification: CoreConfigReloadClassification,
    ) -> None:
        apply_error: str | None = await self.apply_runtime_flags_reload(classification)
        restart_reason: str | None = None
        if classification.has_routing_changes:
            routing_error, routing_restart = assess_routing_only_reload(
                config_dict=classification.config_dict,
                startup_http_client_limits=self.deps.startup_http_client_limits,
                startup_http_client_timeouts=self.deps.startup_http_client_timeouts,
            )
            if routing_error:
                apply_error = append_reload_error(apply_error, routing_error)
            if routing_restart:
                restart_reason = routing_restart
            orchestrator_routing_error = await self.apply_routing_config_via_orchestrator(event)
            if orchestrator_routing_error:
                apply_error = append_reload_error(apply_error, orchestrator_routing_error)
        if classification.has_rate_limiting_changes:
            rate_limit_error = self.apply_rate_limiting_reload(classification.config_dict)
            if rate_limit_error:
                apply_error = append_reload_error(apply_error, rate_limit_error)
        await self.publish_core_configuration_result(event, error=apply_error)
        if restart_reason:
            await self.deps.require_restart(restart_reason, event.path)

    async def _handle_restart_reload(
        self,
        event: ConfigReloadedEvent,
        classification: CoreConfigReloadClassification,
    ) -> None:
        restart_error = "core configuration reload requires restart"
        runtime_flags_error = await self.apply_runtime_flags_reload(classification)
        if runtime_flags_error:
            restart_error = append_reload_error(restart_error, runtime_flags_error)
        if classification.has_routing_changes:
            orchestrator_routing_error = await self.apply_routing_config_via_orchestrator(event)
            if orchestrator_routing_error:
                restart_error = append_reload_error(restart_error, orchestrator_routing_error)
        await self.publish_core_configuration_result(event, restart_error)
        await self.deps.require_restart("Core configuration reload.", event.path)

    async def publish_core_configuration_result(
        self,
        event: ConfigReloadedEvent,
        error: str | None = None,
    ) -> None:
        event_bus = self.deps.coordinator_dependencies.event_bus
        if not event_bus:
            return
        label = "ConfigApplyFailedEvent" if error else "ConfigAppliedEvent"
        await publish_config_apply_event(
            event_bus,
            event,
            error=error,
            logger=self.deps.coordinator_dependencies.logging.logger,
            operation="application_runtime.publish_core_configuration_result",
            message=f"Failed to publish {label} for core configuration",
        )


def _read_bool_path(config_dict: JSONDict, path: tuple[str, ...], *, default: bool) -> bool:
    value = _read_path(config_dict, path)
    return value if isinstance(value, bool) else default


def _read_float_path(config_dict: JSONDict, path: tuple[str, ...], *, default: float) -> float:
    value = _read_path(config_dict, path)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _read_path(config_dict: JSONDict, path: tuple[str, ...]) -> JSONValue | None:
    value: JSONValue | None = config_dict
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
