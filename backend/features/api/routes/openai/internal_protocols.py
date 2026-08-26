"""SoAI - OpenAI route internal protocols [backend/features/api/routes/openai/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from features.agent.runtime.execution_preparation import AgentRuntimePreparation
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("AgentRuntimePreparerProtocol",)


class AgentRuntimePreparerProtocol(Protocol):
    async def __call__(
        self,
        *,
        request: RequestProtocol,
        api_dependencies: ApiDependencies,
        context: RequestContext,
        tool_context: MCPToolContext,
        prepared_agent_request: PreparedExecutionRequest,
        logger: LoggerProtocol,
    ) -> AgentRuntimePreparation: ...
