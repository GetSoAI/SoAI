"""SoAI - Knowledge prompt shared contract [backend/core/rag/knowledge_prompt_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

__all__ = (
    "KNOWLEDGE_ACCESS_TOOL_NAMES",
    "KNOWLEDGE_ALL_TOOL_NAMES",
    "KNOWLEDGE_MANAGEMENT_TOOL_NAMES",
    "KNOWLEDGE_PROMPT_CLAIM_TTL_MS",
    "KNOWLEDGE_PROMPT_ENABLE_TOOLS_GUIDANCE",
    "KNOWLEDGE_PROMPT_MAX_BODY_CHARS",
    "KNOWLEDGE_PROMPT_MAX_DOCUMENT_NAMES_PER_EVENT",
    "KNOWLEDGE_PROMPT_MAX_PENDING_EVENTS",
    "KNOWLEDGE_PROMPT_MAX_VISIBLE_NAME_CHARS",
    "KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE",
    "resolve_knowledge_tool_role",
)

KNOWLEDGE_ACCESS_TOOL_NAMES: tuple[str, ...] = (
    "knowledge_search",
    "knowledge_list",
    "knowledge_config_get",
)
KNOWLEDGE_MANAGEMENT_TOOL_NAMES: tuple[str, ...] = (
    "knowledge_web_fetch",
    "knowledge_reindex",
)
KNOWLEDGE_ALL_TOOL_NAMES: tuple[str, ...] = (
    *KNOWLEDGE_ACCESS_TOOL_NAMES,
    *KNOWLEDGE_MANAGEMENT_TOOL_NAMES,
)
KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE = (
    'Open the chat configuration, go to "Knowledge" tab and upload new files or folders, '
    "in the SoAI WebUI, chat page."
)
KNOWLEDGE_PROMPT_ENABLE_TOOLS_GUIDANCE = (
    'Open the chat configuration, go to "Tools" tab, select the knowledge tools and press '
    '"Save", in the SoAI WebUI, chat page.'
)
KNOWLEDGE_PROMPT_MAX_PENDING_EVENTS = 5
KNOWLEDGE_PROMPT_MAX_DOCUMENT_NAMES_PER_EVENT = 8
KNOWLEDGE_PROMPT_MAX_VISIBLE_NAME_CHARS = 120
KNOWLEDGE_PROMPT_MAX_BODY_CHARS = 2500
KNOWLEDGE_PROMPT_CLAIM_TTL_MS = 600_000


def resolve_knowledge_tool_role(tool_name: str) -> Literal["required_access", "management"] | None:
    if tool_name in KNOWLEDGE_ACCESS_TOOL_NAMES:
        return "required_access"
    if tool_name in KNOWLEDGE_MANAGEMENT_TOOL_NAMES:
        return "management"
    return None
