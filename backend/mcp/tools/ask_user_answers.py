"""SoAI - MCP ask_user completion answers decoding [backend/mcp/tools/ask_user_answers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("require_answers_payload",)


def require_answers_payload(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict):
        raise MCPToolError(-32603, "ask_user task completed without a valid answers payload")
    answers_value = value.get("answers")
    if not isinstance(answers_value, dict):
        raise MCPToolError(-32603, "ask_user task completed without a valid answers payload")
    answers: JSONDict = {}
    for question_id, answer_value in answers_value.items():
        if not isinstance(question_id, str) or not question_id.strip():
            raise MCPToolError(-32603, "ask_user task completed with an invalid question id")
        normalized_question_id = question_id.strip()
        if not isinstance(answer_value, dict):
            raise MCPToolError(-32603, "ask_user task completed with an invalid answer entry")
        answer_entries = answer_value.get("answers")
        if not isinstance(answer_entries, list):
            raise MCPToolError(-32603, "ask_user task completed with an invalid answer entry")
        normalized_entries: list[str] = []
        for entry in answer_entries:
            if not isinstance(entry, str) or not entry.strip():
                raise MCPToolError(-32603, "ask_user task completed with an invalid answer entry")
            normalized_entries.append(entry.strip())
        answers[normalized_question_id] = {"answers": normalized_entries}
    return {"answers": answers}
