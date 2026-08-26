"""SoAI - MCP utility tool: ask_user [backend/mcp/tools/ask_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.ask_user_questions import normalize_questions
from mcp.tools.ask_user_task_lifecycle import (
    OPERATION,
    OPERATION_NOTIFICATION_CLEANUP,
    create_ask_user_task,
    decode_ask_user_task_completion,
)
from mcp.tools.elicitation_task_lifecycle import wait_for_elicitation_task_completion
from mcp.tools.error import get_arg
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_ask_user",)

LOGGER_NAME = "SoAI.mcp.tools.ask_user"
_ALLOWED_KEYS: frozenset[str] = frozenset({"questions"})


async def tool_ask_user(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name="ask_user")
    questions = normalize_questions(get_arg(arguments, "questions"))
    task = await create_ask_user_task(
        utility_tools,
        user_id=user_id,
        conv_id=conv_id,
        questions=questions,
    )
    completed_task = await wait_for_elicitation_task_completion(
        utility_tools,
        interaction_type="ask_user",
        operation=OPERATION,
        operation_notification_cleanup=OPERATION_NOTIFICATION_CLEANUP,
        task_id=task.task_id,
        conv_id=conv_id,
        expires_at_ms=task.ttl_expires_at_ms,
        logger=logger,
    )
    return decode_ask_user_task_completion(completed_task)
