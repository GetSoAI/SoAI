"""SoAI - Subagent background finalization [backend/features/agent/subagents/background_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import SUBAGENT_STATUS_RUNNING
from core.runtime.request_context import RequestContext
from core.timing.epoch import epoch_ms
from core.validation.epoch import require_unix_epoch_ms
from features.agent.subagents.background_finalization_actions import (
    finalize_parent_tool_call_noncritical,
    load_terminal_turn_record,
)
from features.agent.subagents.subagent_lifecycle_event_publication import (
    publish_subagent_terminal_event,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from features.agent.subagents.background_runtime_state import (
        SubagentBackgroundRuntimeState,
    )
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("finalize_subagent_background_execution",)


async def finalize_subagent_background_execution(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
    runtime_state: SubagentBackgroundRuntimeState,
) -> None:
    terminal_turn_record = await load_terminal_turn_record(
        api_dependencies=api_dependencies,
        logger=logger,
        subagent_context=subagent_context,
        subagent_tool_context=subagent_tool_context,
    )
    if runtime_state.final_token_usage is None:
        if not runtime_state.visible_text.strip() and isinstance(terminal_turn_record, dict):
            assistant_text_value = terminal_turn_record.get("assistant_text")
            if isinstance(assistant_text_value, str):
                runtime_state.visible_text = assistant_text_value
        runtime_state.final_token_usage = runtime_state.build_estimated_token_usage()
    terminal_updated_at_ms: int = int(epoch_ms())
    terminal_finished_epoch_ms: int | None = None
    if isinstance(terminal_turn_record, dict):
        terminal_status = str(terminal_turn_record.get("status") or "").strip()
        terminal_finished_at_ms = terminal_turn_record.get("finished_at_ms")
        if (
            terminal_status != SUBAGENT_STATUS_RUNNING
            and isinstance(terminal_finished_at_ms, int)
            and not isinstance(terminal_finished_at_ms, bool)
            and terminal_finished_at_ms >= 0
        ):
            terminal_finished_epoch_ms = require_unix_epoch_ms(
                terminal_finished_at_ms,
                error_message=(
                    "SubagentBackgroundExecutor.terminal_finished_at_ms must be an epoch-millisecond integer."
                ),
            )
            terminal_updated_at_ms = terminal_finished_epoch_ms
    terminal_updated_at_ms = require_unix_epoch_ms(
        max(
            int(terminal_updated_at_ms),
            int(runtime_state.last_published_updated_at_ms or 0),
        ),
        error_message=(
            "SubagentBackgroundExecutor.terminal_updated_at_ms must be an epoch-millisecond integer."
        ),
    )
    if terminal_finished_epoch_ms is not None:
        terminal_updated_at_ms = require_unix_epoch_ms(
            min(
                int(terminal_updated_at_ms),
                int(terminal_finished_epoch_ms),
            ),
            error_message=(
                "SubagentBackgroundExecutor.terminal_updated_at_ms must be an epoch-millisecond integer."
            ),
        )
    if runtime_state.final_token_usage is not None:
        await runtime_state.running_persistence.persist_token_usage(
            runtime_state.final_token_usage,
            updated_at_ms=terminal_updated_at_ms,
        )
    if (
        isinstance(terminal_turn_record, dict)
        and str(terminal_turn_record.get("status") or "").strip() != SUBAGENT_STATUS_RUNNING
    ):
        await finalize_parent_tool_call_noncritical(
            bridge=runtime_state.parent_tool_call_update_bridge,
            turn_record=terminal_turn_record,
            token_usage=runtime_state.final_token_usage,
        )
        await publish_subagent_terminal_event(
            event_bus=api_dependencies.event_bus,
            logger=logger,
            context=subagent_context,
            turn_record=terminal_turn_record,
            token_usage=runtime_state.final_token_usage,
            updated_at_ms_override=terminal_updated_at_ms,
        )
