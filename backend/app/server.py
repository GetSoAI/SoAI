"""SoAI - Application discovery and unified FastAPI server coordinator [backend/app/server.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.api_listener_reservation import reserve_api_listener
from app.application_dependencies import (
    ApplicationLogging,
    ApplicationServerModuleDependencies,
)
from app.internal_protocols import DiscoveryServerProtocol, LifecycleCoordinatorProtocol
from app.server_api_runtime import initialize_unified_api_runtime
from app.server_startup_settings import resolve_unified_server_startup_settings
from app.server_uvicorn_runtime import start_uvicorn_server_runtime
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.licensing.types import Edition
from core.logging.trace import get_logger
from core.meta.instance_identity import resolve_instance_identity
from core.network.hosts import is_bind_all_interfaces_host
from core.runtime.instance_record import (
    read_runtime_instance_record,
    runtime_record_matches_current_process,
    write_runtime_instance_record,
)
from core.security.hardening_collection import (
    SecurityHardeningCollectionDependencies,
    collect_complete_security_hardening_issues,
)
from core.security.hardening_warnings import format_security_hardening_warning
from features.api.middleware.tls_network import get_accessible_network_addresses

if TYPE_CHECKING:
    from app.application_host_instance import ApplicationHostInstance
    from core.config.runtime_config import Config
    from core.hardware.protocols import HardwareManagerProtocol
    from core.licensing.protocols import LicensingRepositoryProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_instance import FilesProtocol
    from core.runtime.protocols import (
        RuntimeFlagsViewProtocol,
        RuntimeStateStoreProtocol,
    )
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "ApplicationServerCoordinator",
    "ApplicationServerCoordinatorDependencies",
)

OPERATION_APPLICATION_SERVER_SHUTDOWN_SERVERS = "application_server.shutdown_servers"
OPERATION_APPLICATION_SERVER_STOP_DISCOVERY_SERVER = "application_server.stop_discovery_server"
LOGGER_NAME = "SoAI.app.server"


@dataclass(slots=True, frozen=True)
class ApplicationServerCoordinatorDependencies:
    logging: ApplicationLogging
    runtime_state: RuntimeStateStoreProtocol
    base_dir: str
    pid_file_path: str
    configuration: Config | None
    runtime_flags: RuntimeFlagsViewProtocol | None
    files: FilesProtocol
    database_users: DatabaseUsersProtocol
    database_plugins: DatabasePluginsProtocol
    database_licensing: LicensingRepositoryProtocol
    logging_manager: LoggingManagerProtocol | None
    lifecycle_coordinator: LifecycleCoordinatorProtocol
    discovery_service: DiscoveryServerProtocol
    hardware_manager: HardwareManagerProtocol | None
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    module_dependencies: ApplicationServerModuleDependencies
    edition: Edition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationServerCoordinatorDependencies",
            base_dir=self.base_dir,
            cancellation_binder=self.cancellation_binder,
            discovery_service=self.discovery_service,
            files=self.files,
            edition=self.edition,
            database_users=self.database_users,
            database_plugins=self.database_plugins,
            database_licensing=self.database_licensing,
            finalizer_tracker=self.finalizer_tracker,
            lifecycle_coordinator=self.lifecycle_coordinator,
            logging=self.logging,
            module_dependencies=self.module_dependencies,
            pid_file_path=self.pid_file_path,
            runtime_state=self.runtime_state,
        )
        if not isinstance(
            self.module_dependencies,
            ApplicationServerModuleDependencies,
        ):
            raise ValidationError("ApplicationServerModuleDependencies are required.")
        if not isinstance(self.base_dir, str) or not self.base_dir.strip():
            raise ValidationError("Application base_dir is required.")


class ApplicationServerCoordinator:
    def __init__(self, deps: ApplicationServerCoordinatorDependencies) -> None:
        self._deps = deps

    async def start_discovery_server(self) -> None:
        configuration = self._deps.configuration
        if configuration is None:
            raise StateError("Configuration not loaded before discovery server startup.")
        runtime_flags = self._deps.runtime_flags
        if runtime_flags is None:
            raise StateError("Runtime flags are not loaded before discovery server startup.")
        runtime_api_endpoint = self._deps.runtime_state.runtime_api_endpoint
        if runtime_api_endpoint is None:
            raise StateError("Runtime API endpoint is unavailable before discovery startup.")
        discovery_host = configuration.require_str("SERVER.HTTP.NETWORK.DISCOVERY_HOST")
        transport_layer_security_options, _user_supplied_tls = (
            self._deps.module_dependencies.prepare_tls_configuration(configuration)
        )
        instance_identity = await resolve_instance_identity(
            self._deps.database_plugins,
            self._deps.database_licensing,
        )
        discovery_started = await self._deps.discovery_service.start(
            discovery_host,
            runtime_api_endpoint.effective_port,
            runtime_api_endpoint.scheme,
            preferred_api_port=runtime_api_endpoint.preferred_port,
            instance_identity=instance_identity,
            edition=self._deps.edition,
            transport_layer_security_options=transport_layer_security_options,
        )
        if not discovery_started and runtime_api_endpoint.fallback_active:
            raise StateError(
                "Discovery is required when the API uses an automatic fallback port.",
            )

    def publish_runtime_endpoint(self) -> None:
        runtime_api_endpoint = self._deps.runtime_state.runtime_api_endpoint
        if runtime_api_endpoint is None:
            raise StateError("Runtime API endpoint is unavailable for publication.")
        runtime_record = read_runtime_instance_record(self._deps.pid_file_path)
        if not runtime_record_matches_current_process(
            runtime_record,
            base_dir=self._deps.base_dir,
            expected_edition=self._deps.edition,
        ):
            raise StateError("Runtime instance record does not belong to the current process.")
        write_runtime_instance_record(
            self._deps.pid_file_path,
            runtime_record.with_api_endpoint(runtime_api_endpoint),
        )

    async def stop_discovery_server(self) -> None:
        discovery_service = self._deps.discovery_service
        if not discovery_service.has_active_server():
            self._deps.logging.logger.debug("Discovery server is not running; skipping stop.")
            return
        self._deps.logging.logger.info("Stopping discovery server...")
        try:
            await discovery_service.stop()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Failed to stop discovery server",
                operation=OPERATION_APPLICATION_SERVER_STOP_DISCOVERY_SERVER,
            )

    async def start_unified_server(self, application_instance: ApplicationHostInstance) -> None:
        configuration = self._deps.configuration
        if configuration is None:
            raise StateError("Configuration not loaded before server startup.")
        server_http_enabled = configuration.get_bool("SERVER.HTTP.ENABLED")
        if not server_http_enabled:
            self._deps.logging.logger.warning(
                "SERVER.HTTP is disabled in configuration. The Unified SoAI Server will not start.",
            )
            self._deps.logging.gui_status("HTTP server disabled; Unified server will not start.")
            return
        logging_manager_instance = self._deps.logging_manager
        if logging_manager_instance is None:
            raise StateError("Logging manager must be initialized before starting servers.")
        database_services = application_instance.services.databases
        hardening_deps = SecurityHardeningCollectionDependencies(
            base_dir=self._deps.base_dir,
            files=self._deps.files,
            database_users=self._deps.database_users,
            database_tokens=database_services.tokens,
            database_api_keys=database_services.api_keys,
            database_mcp_access_tokens=database_services.mcp_access_tokens,
        )
        issues = await collect_complete_security_hardening_issues(
            configuration,
            hardening_deps,
        )
        if issues:
            get_logger(LOGGER_NAME).warning(format_security_hardening_warning(issues))
        self._deps.logging.logger.info("Starting API and WebUI servers...")
        self._deps.logging.gui_status("Starting API and WebUI servers...")
        settings = resolve_unified_server_startup_settings(
            configuration,
            self._deps.module_dependencies,
        )
        reservation = reserve_api_listener(
            settings.host,
            settings.port,
            scheme=settings.scheme,
        )
        runtime_api_endpoint = reservation.endpoint
        api_runtime = initialize_unified_api_runtime(
            application_instance,
            self._deps.module_dependencies,
        )
        self._deps.runtime_state.set_server_runtime(
            runtime_api_endpoint=runtime_api_endpoint,
            tls_user_supplied=settings.user_supplied_transport_layer_security,
            fastapi_app=api_runtime.app,
            request_rate_limiter=api_runtime.request_rate_limiter,
        )
        try:
            await start_uvicorn_server_runtime(
                app=api_runtime.app,
                host=runtime_api_endpoint.bind_host,
                port=runtime_api_endpoint.effective_port,
                sockets=reservation.transfer_sockets(),
                proxy_headers_enabled=api_runtime.proxy_headers_enabled,
                trusted_proxy_networks=api_runtime.trusted_proxy_networks,
                transport_layer_security_options=settings.transport_layer_security_options,
                logging=self._deps.logging,
                lifecycle_coordinator=self._deps.lifecycle_coordinator,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                module_dependencies=self._deps.module_dependencies,
            )
        finally:
            reservation.close()
        if runtime_api_endpoint.fallback_active:
            self._deps.logging.logger.warning(
                "Configured API port %s is occupied; SoAI selected effective port %s. Direct clients configured for the preferred port must be updated.",
                runtime_api_endpoint.preferred_port,
                runtime_api_endpoint.effective_port,
            )
        self._deps.logging.logger.info(
            "Unified SoAI Server started. API and WebUI will be available at %s://%s:%s",
            runtime_api_endpoint.scheme,
            runtime_api_endpoint.bind_host,
            runtime_api_endpoint.effective_port,
        )
        self._deps.logging.gui_status(
            f"Server started at {runtime_api_endpoint.scheme}://{runtime_api_endpoint.bind_host}:{runtime_api_endpoint.effective_port}",
        )
        hardware_manager = self._deps.hardware_manager
        if (
            is_bind_all_interfaces_host(runtime_api_endpoint.bind_host)
            and hardware_manager is not None
        ):
            network_message = get_accessible_network_addresses(
                runtime_api_endpoint.bind_host,
                runtime_api_endpoint.effective_port,
                runtime_api_endpoint.scheme,
                hardware_manager,
            )
            if network_message:
                self._deps.logging.logger.info(network_message)

    async def shutdown_servers(self, timeout: float) -> None:
        if timeout < 0:
            raise ValidationError("Shutdown timeout must be non-negative.")
        lifecycle_coordinator = self._deps.lifecycle_coordinator
        if not lifecycle_coordinator.has_servers():
            self._deps.logging.logger.debug("No active servers registered for shutdown.")
            return
        self._deps.logging.logger.info(
            "Initiating unified server shutdown with a %.2fs timeout.",
            timeout,
        )
        try:
            await lifecycle_coordinator.shutdown_servers(timeout)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Unified server shutdown encountered an error",
                operation=OPERATION_APPLICATION_SERVER_SHUTDOWN_SERVERS,
            )
