"""SoAI - MCP conversation and catalog schemas [backend/features/api/schemas/mcp_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictBool, StrictStr

from core.meta.soai_v1 import SoAIV1StrictModel
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "AutomationMCPToolCatalogResponse",
    "ConversationMCPConfig",
    "ConversationMCPConfigResponse",
    "ConversationMCPConfigUpdate",
    "ConversationMCPKnowledgeState",
    "ConversationMCPToolCatalogResponse",
    "MCPToolCatalogEntry",
    "MessagingMCPToolCatalogResponse",
)


class ConversationMCPConfig(BaseModel):
    default_tools: list[str] = Field(default_factory=list[str])
    plan_tools: list[str] = Field(default_factory=list[str])
    execute_tools: list[str] = Field(default_factory=list[str])
    server_configs: dict[str, bool] = Field(default_factory=dict[str, bool])
    tools_enabled: bool
    tool_approval_required: bool


class ConversationMCPKnowledgeState(BaseModel):
    blocking_reason: (
        Literal[
            "disabled",
            "empty",
            "model_without_tool_calling",
            "missing_required_tools",
        ]
        | None
    ) = None
    rag_enabled: bool
    ready: bool
    force_tools_enabled: bool
    tools_locked: bool
    auto_managed: bool
    document_count: int


class ConversationMCPConfigResponse(ConversationMCPConfig):
    conv_id: str
    knowledge_state: ConversationMCPKnowledgeState


class ConversationMCPConfigUpdate(SoAIV1StrictModel):
    default_tools: list[StrictStr] | None = None
    plan_tools: list[StrictStr] | None = None
    execute_tools: list[StrictStr] | None = None
    server_configs: dict[str, StrictBool] | None = None
    tools_enabled: StrictBool | None = None
    tool_approval_required: StrictBool | None = None


class MCPToolCatalogEntry(BaseModel):
    name: str
    definition: dict[str, PydanticJSONValue] | None
    source: Literal["builtin", "remote"]
    server_id: str | None
    server_name: str
    allowed: bool
    blocked_reason: str | None = None
    enabled_by_default: bool
    enabled_by_plan: bool
    enabled_by_execute: bool
    knowledge_role: Literal["required_access", "management"] | None = None
    icons: list[dict[str, PydanticJSONValue]] | None = None


class ConversationMCPToolCatalogResponse(BaseModel):
    conv_id: str
    tools: list[MCPToolCatalogEntry]
    default_tools: list[str]
    plan_tools: list[str]
    execute_tools: list[str]
    canonical_default_tools: list[str]
    canonical_plan_tools: list[str]
    canonical_execute_tools: list[str]


class AutomationMCPToolCatalogResponse(BaseModel):
    tools: list[MCPToolCatalogEntry]
    execute_tools: list[str]


class MessagingMCPToolCatalogResponse(BaseModel):
    tools: list[MCPToolCatalogEntry]
    default_tools: list[str]
    plan_tools: list[str]
    execute_tools: list[str]
