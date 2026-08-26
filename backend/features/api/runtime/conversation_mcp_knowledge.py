"""SoAI - Conversation knowledge-managed MCP policy [backend/features/api/runtime/conversation_mcp_knowledge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError
from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
from core.mcp.tool_entries import SOAI_MCP_SERVER_ID
from core.rag.conversation_config import read_rag_enabled_from_config
from core.rag.knowledge_prompt_contract import (
    KNOWLEDGE_ACCESS_TOOL_NAMES,
)
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.model_tool_calling import model_supports_tool_calling

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.internal_protocols import (
        ConversationMCPKnowledgeStateProtocol,
    )

    type KnowledgeBlockingReason = Literal[
        "disabled",
        "empty",
        "model_without_tool_calling",
        "missing_required_tools",
    ]

__all__ = (
    "ConversationKnowledgeMCPState",
    "apply_knowledge_managed_mcp_overlay",
    "build_knowledge_state_payload",
    "resolve_conversation_knowledge_mcp_state",
    "strip_knowledge_managed_mcp_overlay",
)

_KNOWLEDGE_BLOCKING_DISABLED: Literal["disabled"] = "disabled"
_KNOWLEDGE_BLOCKING_EMPTY: Literal["empty"] = "empty"
_KNOWLEDGE_BLOCKING_MODEL_WITHOUT_TOOL_CALLING: Literal["model_without_tool_calling"] = (
    "model_without_tool_calling"
)
_KNOWLEDGE_BLOCKING_MISSING_REQUIRED_TOOLS: Literal["missing_required_tools"] = (
    "missing_required_tools"
)


@dataclass(frozen=True, slots=True)
class ConversationKnowledgeMCPState:
    rag_enabled: bool
    document_count: int
    auto_managed: bool
    tools_locked: bool
    force_tools_enabled: bool
    ready: bool
    blocking_reason: KnowledgeBlockingReason | None


def build_knowledge_state_payload(
    *,
    rag_enabled: bool,
    document_count: int,
    auto_managed: bool,
    tools_locked: bool,
    force_tools_enabled: bool,
    ready: bool,
    blocking_reason: KnowledgeBlockingReason | None,
) -> JSONDict:
    return {
        "rag_enabled": rag_enabled,
        "document_count": document_count,
        "auto_managed": auto_managed,
        "tools_locked": tools_locked,
        "force_tools_enabled": force_tools_enabled,
        "ready": ready,
        "blocking_reason": blocking_reason,
    }


async def resolve_conversation_knowledge_mcp_state(
    *,
    api_dependencies: ApiDependencies,
    conv_id: str,
    model_id: str | None,
    available_tool_names: set[str] | None = None,
) -> ConversationKnowledgeMCPState:
    raw_counts = await api_dependencies.database_files.get_rag_counts_for_conversation(
        conv_id,
    )
    if not isinstance(raw_counts, dict):
        raise StateError("Conversation RAG counts are invalid.")
    document_count_value = raw_counts.get("document_count")
    if not is_strict_int(document_count_value):
        raise StateError("Conversation RAG document count is invalid.")
    document_count = max(0, int(document_count_value))
    raw_config = await api_dependencies.database_files.get_rag_config(conv_id)
    rag_enabled = read_rag_enabled_from_config(raw_config)
    if not rag_enabled:
        return ConversationKnowledgeMCPState(
            rag_enabled=False,
            document_count=document_count,
            auto_managed=False,
            tools_locked=False,
            force_tools_enabled=False,
            ready=False,
            blocking_reason=_KNOWLEDGE_BLOCKING_DISABLED,
        )
    if document_count <= 0:
        return ConversationKnowledgeMCPState(
            rag_enabled=True,
            document_count=0,
            auto_managed=False,
            tools_locked=False,
            force_tools_enabled=False,
            ready=False,
            blocking_reason=_KNOWLEDGE_BLOCKING_EMPTY,
        )
    if available_tool_names is not None and any(
        tool_name not in available_tool_names for tool_name in KNOWLEDGE_ACCESS_TOOL_NAMES
    ):
        return ConversationKnowledgeMCPState(
            rag_enabled=True,
            document_count=document_count,
            auto_managed=False,
            tools_locked=False,
            force_tools_enabled=False,
            ready=False,
            blocking_reason=_KNOWLEDGE_BLOCKING_MISSING_REQUIRED_TOOLS,
        )
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    ready = normalized_model_id is not None and await model_supports_tool_calling(
        api_dependencies,
        normalized_model_id,
    )
    if not ready:
        return ConversationKnowledgeMCPState(
            rag_enabled=True,
            document_count=document_count,
            auto_managed=False,
            tools_locked=False,
            force_tools_enabled=False,
            ready=False,
            blocking_reason=_KNOWLEDGE_BLOCKING_MODEL_WITHOUT_TOOL_CALLING,
        )
    return ConversationKnowledgeMCPState(
        rag_enabled=True,
        document_count=document_count,
        auto_managed=True,
        tools_locked=True,
        force_tools_enabled=True,
        ready=ready,
        blocking_reason=None,
    )


def apply_knowledge_managed_mcp_overlay(
    normalized_mcp: NormalizedAgentMCPConfig,
    knowledge_state: ConversationKnowledgeMCPState,
) -> NormalizedAgentMCPConfig:
    if not knowledge_state.auto_managed:
        return normalized_mcp
    server_configs = dict(normalized_mcp.server_configs)
    server_configs[SOAI_MCP_SERVER_ID] = True
    return NormalizedAgentMCPConfig(
        default_tools=_union_required_knowledge_tools(normalized_mcp.default_tools),
        plan_tools=_union_required_knowledge_tools(normalized_mcp.plan_tools),
        execute_tools=_union_required_knowledge_tools(normalized_mcp.execute_tools),
        server_configs=server_configs,
        tools_enabled=True,
        tool_approval_required=normalized_mcp.tool_approval_required,
    )


def strip_knowledge_managed_mcp_overlay(
    *,
    merged_payload: JSONDict,
    stored_normalized_mcp: NormalizedAgentMCPConfig,
    knowledge_state: ConversationMCPKnowledgeStateProtocol,
    updates: JSONDict,
) -> JSONDict:
    if not knowledge_state.auto_managed:
        return dict(merged_payload)
    payload = dict(merged_payload)
    payload["default_tools"] = _resolve_persisted_tool_list(
        field_name="default_tools",
        merged_payload=payload,
        stored_tools=stored_normalized_mcp.default_tools,
        updates=updates,
    )
    payload["plan_tools"] = _resolve_persisted_tool_list(
        field_name="plan_tools",
        merged_payload=payload,
        stored_tools=stored_normalized_mcp.plan_tools,
        updates=updates,
    )
    payload["execute_tools"] = _resolve_persisted_tool_list(
        field_name="execute_tools",
        merged_payload=payload,
        stored_tools=stored_normalized_mcp.execute_tools,
        updates=updates,
    )
    if "tools_enabled" not in updates:
        payload["tools_enabled"] = stored_normalized_mcp.tools_enabled
    payload["server_configs"] = _resolve_persisted_server_configs(
        merged_payload=payload,
        stored_server_configs=stored_normalized_mcp.server_configs,
        updates=updates,
    )
    return payload


def _union_required_knowledge_tools(selected_tools: list[str]) -> list[str]:
    merged = list(selected_tools)
    for tool_name in KNOWLEDGE_ACCESS_TOOL_NAMES:
        if tool_name not in merged:
            merged.append(tool_name)
    return merged


def _resolve_persisted_tool_list(
    *,
    field_name: str,
    merged_payload: JSONDict,
    stored_tools: list[str],
    updates: JSONDict,
) -> list[str]:
    if field_name not in updates:
        return list(stored_tools)
    raw_value = merged_payload.get(field_name)
    if not isinstance(raw_value, list):
        return list(stored_tools)
    normalized: list[str] = []
    for entry in raw_value:
        if not isinstance(entry, str):
            continue
        tool_name = entry.strip()
        if not tool_name or tool_name in KNOWLEDGE_ACCESS_TOOL_NAMES or tool_name in normalized:
            continue
        normalized.append(tool_name)
    return normalized


def _resolve_persisted_server_configs(
    *,
    merged_payload: JSONDict,
    stored_server_configs: dict[str, bool],
    updates: JSONDict,
) -> dict[str, bool]:
    if "server_configs" not in updates:
        return dict(stored_server_configs)
    raw_value = merged_payload.get("server_configs")
    if not isinstance(raw_value, dict):
        return dict(stored_server_configs)
    normalized: dict[str, bool] = {}
    for server_id, enabled in raw_value.items():
        if not isinstance(server_id, str) or not server_id.strip():
            continue
        if not isinstance(enabled, bool):
            continue
        normalized_server_id = server_id.strip()
        if normalized_server_id == SOAI_MCP_SERVER_ID:
            if SOAI_MCP_SERVER_ID in stored_server_configs:
                normalized[normalized_server_id] = stored_server_configs[SOAI_MCP_SERVER_ID]
            continue
        normalized[normalized_server_id] = enabled
    return normalized
