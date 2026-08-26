"""SoAI - Subagent background runtime state [backend/features/agent/subagents/background_runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.runtime.request_context import RequestContext
from core.timing.epoch import epoch_ms
from features.agent.subagents.background_running_persistence import (
    SubagentRunningTurnPersistence,
)
from features.agent.subagents.parent_tool_call_update_models import (
    build_live_subagent_record,
)
from features.agent.subagents.parent_tool_call_updates import (
    SubagentParentToolCallUpdateBridge,
)
from features.agent.subagents.reads import load_subagent_turn_record_noncritical
from features.agent.subagents.snapshots import (
    build_subagent_snapshot,
    trim_subagent_result_excerpt,
)
from features.agent.subagents.subagent_running_event_publication import (
    publish_subagent_running_event,
)
from features.agent.subagents.token_usage import build_estimated_subagent_token_usage

if TYPE_CHECKING:
    from core.execution.protocols import SubagentSnapshot
    from core.logging.protocols import LoggerProtocol
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("SubagentBackgroundRuntimeState",)


@dataclass(slots=True)
class SubagentBackgroundRuntimeState:
    api_dependencies: ApiDependencies
    logger: LoggerProtocol
    subagent_context: RequestContext
    subagent_tool_context: MCPToolContext
    requested_model: str
    token_estimation_profile: TokenEstimationProfile
    running_persistence: SubagentRunningTurnPersistence
    visible_text: str = ""
    preview_text: str = ""
    prompt_tokens: int = 0
    prompt_tokens_capped: bool = False
    prompt_tokens_capped_reason: str | None = None
    prompt_tokens_precision: Literal["exact", "estimated"] = "exact"
    final_token_usage: JSONDict | None = None
    last_published_updated_at_ms: int = 0
    parent_tool_call_update_bridge: SubagentParentToolCallUpdateBridge | None = None

    def build_estimated_token_usage(self) -> JSONDict:
        return build_estimated_subagent_token_usage(
            prompt_token_counter=self.api_dependencies.prompt_token_counter,
            requested_model=self.requested_model,
            prompt_tokens=self.prompt_tokens,
            prompt_tokens_capped=self.prompt_tokens_capped,
            prompt_tokens_capped_reason=self.prompt_tokens_capped_reason,
            prompt_tokens_precision=self.prompt_tokens_precision,
            visible_text=self.visible_text,
            token_estimation_profile=self.token_estimation_profile,
        )

    async def publish_running_preview(self, *, result_text_delta: str | None) -> None:
        updated_at_ms = epoch_ms()
        self.last_published_updated_at_ms = max(self.last_published_updated_at_ms, updated_at_ms)
        await self.running_persistence.maybe_persist_running_assistant_text(
            self.visible_text,
            updated_at_ms=updated_at_ms,
        )
        token_usage = self.build_estimated_token_usage()
        persisted_turn = await self.running_persistence.persist_token_usage(
            token_usage,
            updated_at_ms=updated_at_ms,
        )
        turn_record = (
            persisted_turn
            if persisted_turn is not None
            else await load_subagent_turn_record_noncritical(
                database_agent_turns=self.api_dependencies.database_agent_turns,
                logger=self.logger,
                trace_id=self.subagent_context.trace_id,
                conv_id=self.subagent_tool_context.conv_id,
                user_id=self.subagent_tool_context.user_id,
                subagent_id=str(self.subagent_context.agent_turn_id or ""),
            )
        )
        turn_snapshot = build_subagent_snapshot(turn_record)
        if turn_snapshot is None:
            return
        await self._publish_parent_meta_snapshot_noncritical(
            snapshot=turn_snapshot,
            token_usage=token_usage,
        )
        await publish_subagent_running_event(
            event_bus=self.api_dependencies.event_bus,
            logger=self.logger,
            snapshot=turn_snapshot,
            user_id=self.subagent_context.user_id,
            conv_id=self.subagent_tool_context.conv_id,
            result_text=self.preview_text or None,
            result_text_delta=result_text_delta,
            error_message=None,
            token_usage=token_usage,
            updated_at_ms_override=updated_at_ms,
        )

    async def handle_preview_deltas(self, deltas: tuple[str, ...]) -> None:
        self.visible_text += "".join(deltas)
        self.preview_text = trim_subagent_result_excerpt(self.visible_text) or self.preview_text
        delta_text = "".join(segment for segment in deltas if isinstance(segment, str) and segment)
        if self.parent_tool_call_update_bridge is not None and delta_text:
            await self.parent_tool_call_update_bridge.add_text_block_delta(delta_text, epoch_ms())
        await self.publish_running_preview(result_text_delta=delta_text or None)

    async def handle_stream_initialized(
        self,
        initialized_prompt_tokens: int,
        initialized_prompt_tokens_capped: bool,
        initialized_prompt_tokens_capped_reason: str | None,
        initialized_prompt_tokens_precision: Literal["exact", "estimated"],
    ) -> None:
        self.prompt_tokens = initialized_prompt_tokens
        self.prompt_tokens_capped = initialized_prompt_tokens_capped
        self.prompt_tokens_capped_reason = initialized_prompt_tokens_capped_reason
        self.prompt_tokens_precision = initialized_prompt_tokens_precision
        await self.publish_running_preview(result_text_delta=None)

    async def handle_raw_bytes(self, chunk: bytes) -> None:
        _ = chunk

    async def _publish_parent_meta_snapshot_noncritical(
        self,
        *,
        snapshot: SubagentSnapshot,
        token_usage: JSONDict,
    ) -> None:
        bridge = self.parent_tool_call_update_bridge
        if bridge is None:
            return
        live_record = build_live_subagent_record(
            snapshot=snapshot,
            result_text=self.visible_text or None,
            token_usage=token_usage,
        )
        await bridge.publish_subagent_state_noncritical(subagent_record=live_record)
