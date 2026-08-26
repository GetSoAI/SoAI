"""SoAI - Background shell-session watch service assembly [backend/app/composition/build_shell_background_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.mcp.protocols_main import ShellBackgroundServiceProtocol
from features.api.runtime.container.types import ApiDependencies
from mcp.tools.shell_background.service import (
    ShellBackgroundService,
    ShellBackgroundServiceDependencies,
)

__all__ = ("build_shell_background_service",)

LOGGER_NAME = "SoAI.app.composition.build_shell_background_service"


def build_shell_background_service(
    api_dependencies: ApiDependencies,
) -> ShellBackgroundServiceProtocol:
    utility_tools = api_dependencies.mcp_server.utility_tools
    service = ShellBackgroundService(
        ShellBackgroundServiceDependencies(
            database_tool_calls=api_dependencies.database_tool_calls,
            task_registry=api_dependencies.task_registry,
            event_bus=api_dependencies.event_bus,
            task_cancellation_binder=api_dependencies.task_cancellation_binder,
            task_finalizer_tracker=api_dependencies.task_finalizer_tracker,
            logger=get_logger(LOGGER_NAME),
        ),
    )
    utility_tools.attach_shell_background_service(service)
    return service
