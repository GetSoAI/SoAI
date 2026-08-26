"""SoAI - MCP content envelope builders [backend/core/mcp/content_envelopes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json import serialize_json_pretty_sorted_strict
from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_json_resource_content",
    "build_resource_contents_result",
    "build_text_prompt_result",
)


def build_json_resource_content(*, uri: str, payload: JSONValue) -> JSONDict:
    return {
        "uri": uri,
        "mimeType": "application/json",
        "text": serialize_json_pretty_sorted_strict(payload),
    }


def build_resource_contents_result(*contents: JSONDict) -> JSONDict:
    return {"contents": list(contents)}


def build_text_prompt_result(*, description: str, text: str) -> JSONDict:
    return {
        "description": description,
        "messages": [{"role": "user", "content": [{"type": "text", "text": text}]}],
    }
