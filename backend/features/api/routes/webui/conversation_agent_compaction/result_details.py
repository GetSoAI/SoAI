"""SoAI - Manual compaction result-details builder [backend/features/api/routes/webui/conversation_agent_compaction/result_details.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.protocols import LoggerProtocol
from core.openai.pinned_prefix import strip_leading_pinned_prefix
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries,
)
from core.tool_calls.context_compaction_boundary_state import (
    build_context_compaction_boundary_state,
)
from core.types.json import JSONDict
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_context_window,
)
from features.api.routes.webui.conversation_agent_compaction.summarizer_pipeline import (
    ManualCompactionSummaryResult,
)
from features.api.runtime.context import ApiContext

__all__ = ("resolve_manual_compaction_result_details",)

OPERATION_WEBUI_AGENT_COMPACT_MANUAL_FETCH_CONVERSATION_TITLE = (
    "webui.agent_compaction.fetch_conversation_title"
)


async def resolve_manual_compaction_result_details(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    model: str,
    context_window_tokens: int,
    compaction_limit: int | None,
    summarizer_budget: int,
    source_messages: list[JSONDict],
    summary: ManualCompactionSummaryResult | None,
) -> JSONDict:
    source_message_body = strip_leading_pinned_prefix(source_messages)
    boundary_resolution = resolve_context_compaction_boundaries(
        source_message_body,
        strip_leading_pinned_prefix=False,
    )
    effective_source_messages = boundary_resolution.messages
    conversation_title: str | None = None
    try:
        conversation_record = (
            await api_context.dependencies.database_conversations.get_conversation(
                conv_id,
                user_id,
            )
        )
        title_value = (
            conversation_record.get("title") if isinstance(conversation_record, dict) else None
        )
        conversation_title = (
            str(title_value).strip()
            if isinstance(title_value, str) and title_value.strip()
            else None
        )
    except (AttributeError, KeyError, TypeError, ValueError) as title_exception:
        coerced = coerce_to_soai_error(
            title_exception,
            operation=OPERATION_WEBUI_AGENT_COMPACT_MANUAL_FETCH_CONVERSATION_TITLE,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Manual compaction title metadata lookup failed (non-critical).",
            operation=OPERATION_WEBUI_AGENT_COMPACT_MANUAL_FETCH_CONVERSATION_TITLE,
            level="debug",
            details={"conv_id": str(conv_id)},
        )
    compaction_budget = resolve_compaction_budget_from_context_window(
        config=api_context.dependencies.config,
        context_window_tokens=context_window_tokens,
    )
    details: JSONDict = {
        "trigger": "manual",
        "conversation_id": str(conv_id),
        "conversation_title": conversation_title,
        "model": str(model),
        "context_window_tokens": int(compaction_budget.context_window_tokens),
        "reserved_output_tokens": int(compaction_budget.reserved_output_tokens),
        "trigger_margin_ratio": float(compaction_budget.trigger_margin_ratio),
        "post_compact_margin_ratio": float(compaction_budget.post_compact_margin_ratio),
        "dropped_message_count": 0,
        "tool_stub_count": 0,
        "truncated_message_count": 0,
        "compaction_limit_prompt_tokens": (
            int(compaction_limit) if compaction_limit is not None else None
        ),
        "summarizer_budget_prompt_tokens": int(summarizer_budget),
        "source_message_count": len(effective_source_messages),
    }
    details.update(build_context_compaction_boundary_state(effective_source_messages))
    if summary is None:
        return details
    details.update(
        {
            "dropped_message_count": max(0, int(summary.source_message_count) - 1),
            "target_prompt_tokens": int(summary.target_prompt_tokens),
            "prompt_tokens_before": int(summary.source_prompt_tokens),
            "prompt_tokens_after": int(summary.summary_prompt_tokens),
            "source_message_count": int(summary.source_message_count),
            "source_serialized_chars": int(summary.source_serialized_chars),
            "summary_chars": int(summary.summary_chars),
            "summary_source": "llm",
        },
    )
    return details
