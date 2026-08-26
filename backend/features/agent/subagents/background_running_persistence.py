"""SoAI - Subagent running turn persistence [backend/features/agent/subagents/background_running_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.request_context import RequestContext
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("SubagentRunningTurnPersistence",)

OPERATION_SUBAGENT_PERSIST_TOKEN_USAGE = "agent.subagents.background.persist_token_usage"
OPERATION_SUBAGENT_PERSIST_ASSISTANT_TEXT = "agent.subagents.background.persist_assistant_text"

_SUBAGENT_ASSISTANT_TEXT_PERSIST_MIN_CHARS = 512
_SUBAGENT_ASSISTANT_TEXT_PERSIST_MIN_INTERVAL_MS = 1500


@dataclass(slots=True)
class SubagentRunningTurnPersistence:
    api_dependencies: ApiDependencies
    logger: LoggerProtocol
    subagent_context: RequestContext
    subagent_tool_context: MCPToolContext
    assistant_text_persisted_chars: int = 0
    assistant_text_last_persisted_monotonic_ms: int = 0

    async def persist_token_usage(
        self,
        token_usage: JSONDict,
        *,
        updated_at_ms: int,
    ) -> JSONDict | None:
        turn_id = str(self.subagent_context.agent_turn_id or "").strip()
        execution_token = str(self.subagent_context.agent_turn_execution_token or "").strip()
        if not turn_id or not execution_token:
            return None
        try:
            return await self.api_dependencies.database_agent_turns.write_turn_token_usage(
                conv_id=self.subagent_tool_context.conv_id,
                user_id=self.subagent_tool_context.user_id,
                turn_id=turn_id,
                execution_token=execution_token,
                token_usage=token_usage,
                updated_at_ms=updated_at_ms,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SUBAGENT_PERSIST_TOKEN_USAGE,
            )
            log_handled_exception(
                self.logger,
                coerced,
                message="Failed to persist subagent token usage (non-critical).",
                trace_id=self.subagent_context.trace_id,
                operation=OPERATION_SUBAGENT_PERSIST_TOKEN_USAGE,
                level="warning",
                details={"conv_id": self.subagent_tool_context.conv_id, "turn_id": turn_id},
            )
            return None

    async def persist_assistant_text_noncritical(
        self,
        assistant_text: str,
        *,
        updated_at_ms: int,
    ) -> JSONDict | None:
        turn_id = str(self.subagent_context.agent_turn_id or "").strip()
        execution_token = str(self.subagent_context.agent_turn_execution_token or "").strip()
        if not turn_id or not execution_token:
            return None
        try:
            return await self.api_dependencies.database_agent_turns.write_turn_assistant_text(
                conv_id=self.subagent_tool_context.conv_id,
                user_id=self.subagent_tool_context.user_id,
                turn_id=turn_id,
                execution_token=execution_token,
                assistant_text=assistant_text,
                updated_at_ms=updated_at_ms,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SUBAGENT_PERSIST_ASSISTANT_TEXT,
            )
            log_handled_exception(
                self.logger,
                coerced,
                message="Failed to persist subagent assistant_text (non-critical).",
                trace_id=self.subagent_context.trace_id,
                operation=OPERATION_SUBAGENT_PERSIST_ASSISTANT_TEXT,
                level="warning",
                details={"conv_id": self.subagent_tool_context.conv_id, "turn_id": turn_id},
            )
            return None

    async def maybe_persist_running_assistant_text(
        self,
        assistant_text: str,
        *,
        updated_at_ms: int,
    ) -> None:
        normalized_text = assistant_text
        if not normalized_text:
            return
        now_monotonic_ms = monotonic_ms()
        if self.assistant_text_persisted_chars != 0:
            delta_chars = len(normalized_text) - self.assistant_text_persisted_chars
            interval_ms = max(0, now_monotonic_ms - self.assistant_text_last_persisted_monotonic_ms)
            if (
                delta_chars < _SUBAGENT_ASSISTANT_TEXT_PERSIST_MIN_CHARS
                and interval_ms < _SUBAGENT_ASSISTANT_TEXT_PERSIST_MIN_INTERVAL_MS
            ):
                return
        persisted = await self.persist_assistant_text_noncritical(
            normalized_text,
            updated_at_ms=updated_at_ms,
        )
        if persisted is None:
            return
        self.assistant_text_persisted_chars = len(normalized_text)
        self.assistant_text_last_persisted_monotonic_ms = now_monotonic_ms
