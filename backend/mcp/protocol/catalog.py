"""SoAI - MCP resource templates and prompt catalog definitions [backend/mcp/protocol/catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_rag_resource_uri_definitions, build_tool_icon_entry
from mcp.calendar.resource_catalog import (
    build_calendar_resource_metadata,
    build_calendar_resource_templates,
)
from mcp.mail.resource_catalog import (
    build_mail_resource_metadata,
    build_mail_resource_templates,
)
from mcp.protocol.icons import ICON_LIST, get_icon_svg

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_prompt_definitions",
    "build_rag_resource_templates",
    "build_resource_metadata",
    "build_resource_templates",
)


def build_rag_resource_templates() -> list[JSONDict]:
    templates: list[JSONDict] = []
    for definition in build_rag_resource_uri_definitions():
        icon_src = get_icon_svg(definition.icon_name)
        templates.append(
            {
                "uriTemplate": definition.uri_template,
                "name": definition.display_name,
                "title": definition.title,
                "description": definition.description,
                "mimeType": definition.mime_type,
                "icons": [build_tool_icon_entry(icon_src)],
                "annotations": {
                    "audience": list(definition.audience),
                    "priority": definition.priority,
                },
            },
        )
    return templates


def build_resource_templates() -> tuple[JSONDict, ...]:
    templates: list[JSONDict] = [
        {
            "uriTemplate": "soai://models/{model_id}",
            "name": "Model Details",
            "title": "Model Details",
            "description": "Get details for a specific SoAI model",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(get_icon_svg("model"), include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.8},
        },
        {
            "uriTemplate": "soai://webui/prompts",
            "name": "WebUI Prompts",
            "title": "Saved Prompts",
            "description": "List your saved WebUI prompts (supports query params: q, color, limit)",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(get_icon_svg("bookmark"), include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.6},
        },
        {
            "uriTemplate": "soai://webui/prompts/{prompt_id}",
            "name": "WebUI Prompt",
            "title": "Saved Prompt",
            "description": "Get a single saved WebUI prompt by id",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(get_icon_svg("bookmark"), include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.6},
        },
    ]
    templates.extend(build_mail_resource_templates())
    templates.extend(build_calendar_resource_templates())
    templates.extend(build_rag_resource_templates())
    return tuple(templates)


def build_resource_metadata() -> JSONDict:
    metadata: JSONDict = {
        "soai://models": {
            "name": "Available Models",
            "title": "Available Models",
            "description": "List of all models available in SoAI",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_LIST)],
            "annotations": {"audience": ["user", "assistant"], "priority": 1.0},
        },
        "soai://plugins": {
            "name": "Installed Plugins",
            "title": "Installed Plugins",
            "description": "List of all installed SoAI plugins",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(get_icon_svg("puzzle"))],
            "annotations": {"audience": ["user"], "priority": 0.7},
        },
        "soai://system_status": {
            "name": "System Status",
            "title": "System Status",
            "description": "Current SoAI system status",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(get_icon_svg("gauge"))],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.9},
        },
    }
    metadata.update(build_mail_resource_metadata())
    metadata.update(build_calendar_resource_metadata())
    return metadata


def build_prompt_definitions() -> dict[str, JSONDict]:
    return {
        "system_overview": {
            "name": "system_overview",
            "title": "System Overview",
            "description": "Get a comprehensive overview of the SoAI system status including models, plugins, and hardware",
            "icons": [build_tool_icon_entry(get_icon_svg("gauge"))],
            "arguments": [],
        },
        "model_selection": {
            "name": "model_selection",
            "title": "Model Selection Assistant",
            "description": "Get assistance selecting the best model for your task based on requirements",
            "icons": [build_tool_icon_entry(get_icon_svg("model"))],
            "arguments": [
                {
                    "name": "task_type",
                    "description": "The type of task (e.g., 'chat', 'coding', 'analysis', 'creative')",
                    "required": False,
                },
                {
                    "name": "context_length",
                    "description": "Required context window size in tokens",
                    "required": False,
                },
            ],
        },
        "plugin_info": {
            "name": "plugin_info",
            "title": "Plugin Information",
            "description": "Get detailed information about a specific SoAI plugin",
            "icons": [build_tool_icon_entry(get_icon_svg("puzzle"))],
            "arguments": [
                {
                    "name": "plugin_name",
                    "description": "The name of the plugin to get information about",
                    "required": True,
                },
            ],
        },
        "rag_document_summary": {
            "name": "rag_document_summary",
            "title": "Summarize RAG Document",
            "description": "Generate a comprehensive summary of a specific document in the knowledge base",
            "icons": [build_tool_icon_entry(get_icon_svg("doc"))],
            "arguments": [
                {
                    "name": "conv_id",
                    "description": "SoAI conversation id (e.g., 'conv_<uuid>')",
                    "required": True,
                },
                {
                    "name": "document_id",
                    "description": "UUID of the document to summarize",
                    "required": True,
                },
                {
                    "name": "max_chunks",
                    "description": "Maximum number of chunks to include (default: 50)",
                    "required": False,
                },
            ],
        },
        "rag_topic_extraction": {
            "name": "rag_topic_extraction",
            "title": "Extract Key Topics from Knowledge Base",
            "description": "Identify and extract main topics from conversation's RAG documents",
            "icons": [build_tool_icon_entry(get_icon_svg("list"))],
            "arguments": [
                {
                    "name": "conv_id",
                    "description": "SoAI conversation id (e.g., 'conv_<uuid>')",
                    "required": True,
                },
                {
                    "name": "top_n",
                    "description": "Number of top topics to extract (default: 10)",
                    "required": False,
                },
            ],
        },
        "rag_question_answering": {
            "name": "rag_question_answering",
            "title": "Answer Question Using RAG",
            "description": "Answer a question using only information from the knowledge base with source citations",
            "icons": [build_tool_icon_entry(get_icon_svg("search"))],
            "arguments": [
                {
                    "name": "conv_id",
                    "description": "SoAI conversation id (e.g., 'conv_<uuid>')",
                    "required": True,
                },
                {
                    "name": "question",
                    "description": "The question to answer",
                    "required": True,
                },
                {
                    "name": "top_k",
                    "description": "Number of relevant chunks to retrieve (default: 5)",
                    "required": False,
                },
            ],
        },
        "rag_compare_sources": {
            "name": "rag_compare_sources",
            "title": "Compare Information Across Sources",
            "description": "Compare how different sources in the knowledge base address a topic",
            "icons": [build_tool_icon_entry(get_icon_svg("bookmark"))],
            "arguments": [
                {
                    "name": "conv_id",
                    "description": "SoAI conversation id (e.g., 'conv_<uuid>')",
                    "required": True,
                },
                {
                    "name": "topic",
                    "description": "The topic to compare across sources",
                    "required": True,
                },
                {
                    "name": "document_ids",
                    "description": "List of document UUIDs to compare (optional - uses all if not specified)",
                    "required": False,
                },
            ],
        },
    }
