"""SoAI - Bootstrap state shared fields [backend/app/composition/bootstrap_state_core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationLogging, ApplicationPaths, ApplicationSecurity
from app.types_services_database import DatabaseServices
from core.config.protocols import ConfigManagerProtocol
from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggingManagerProtocol
from core.state.protocols import RestartStateManagerProtocol
from core.tasks.protocols import TaskTypeRoutingServiceProtocol

if TYPE_CHECKING:
    from app.composition.build_config import ConfigurationFoundation
    from app.composition.build_runtime import RuntimeFoundation

__all__ = ("BootstrapStateCore",)


@dataclass(frozen=True, slots=True)
class BootstrapStateCore:
    runtime_foundation: RuntimeFoundation
    configuration_foundation: ConfigurationFoundation
    task_type_routing_service: TaskTypeRoutingServiceProtocol
    event_bus: EventBusProtocol
    log_manager: LoggingManagerProtocol
    logging_instance: ApplicationLogging
    restart_state_manager: RestartStateManagerProtocol
    paths: ApplicationPaths
    security: ApplicationSecurity
    database_services: DatabaseServices
    config_manager: ConfigManagerProtocol
