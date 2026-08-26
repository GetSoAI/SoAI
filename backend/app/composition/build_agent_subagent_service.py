"""SoAI - Subagent service assembly [backend/app/composition/build_agent_subagent_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.protocols import AgentSubagentServiceProtocol
from core.logging.trace import get_logger
from features.agent.subagents.background import (
    SubagentBackgroundExecutor,
    SubagentBackgroundExecutorDependencies,
)
from features.agent.subagents.coordinator.service import (
    AgentSubagentService,
    AgentSubagentServiceDependencies,
)
from features.api.runtime.container.types import ApiDependencies

__all__ = ("build_agent_subagent_service",)

LOGGER_NAME = "SoAI.app.composition.build_agent_subagent_service"


def build_agent_subagent_service(
    api_dependencies: ApiDependencies,
) -> AgentSubagentServiceProtocol:
    utility_tools = api_dependencies.mcp_server.utility_tools
    background_executor = SubagentBackgroundExecutor(
        SubagentBackgroundExecutorDependencies(
            api_dependencies=api_dependencies,
            logger=get_logger(LOGGER_NAME),
        ),
    )
    service = AgentSubagentService(
        AgentSubagentServiceDependencies(
            api_dependencies=api_dependencies,
            active_request_context=utility_tools.active_request_context,
            active_tool_call_context=utility_tools.active_tool_call_context,
            background_executor=background_executor,
        ),
    )
    utility_tools.attach_subagent_service(service)
    return service
