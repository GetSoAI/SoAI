"""SoAI - Optional agent context compaction summarizer preparation [backend/features/api/routes/openai/agent_compaction_optional_summarizer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent_mode import is_agent_mode
from core.prompts.system_prompts import get_agent_compaction_summary_system_text_v1
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.tasks.type_catalog import TaskTypeId
from features.agent.session.compaction_budget import (
    resolve_compaction_summary_prompt_budget_from_context_window,
)
from features.api.routes.openai.compaction.summarizer import (
    prepare_agent_compaction_summarizer,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies

__all__ = ("prepare_optional_compaction_summarizer",)


def prepare_optional_compaction_summarizer(
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    request_json: JSONDict,
    mode: str,
    compaction_context_window_tokens: int | None,
    task_type: TaskTypeId,
    owner_type: str,
    owner_id: str,
) -> Callable[[list[JSONDict]], Awaitable[str]] | None:
    if not is_agent_mode(mode):
        return None
    if compaction_context_window_tokens is None:
        return None
    requested_model = request_json.get("model")
    model_id = requested_model if isinstance(requested_model, str) else None
    if model_id is None:
        return None
    summarizer_budget = resolve_compaction_summary_prompt_budget_from_context_window(
        config=api_context.dependencies.config,
        context_window_tokens=compaction_context_window_tokens,
    )
    return prepare_agent_compaction_summarizer(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        model=model_id,
        system_prompt_text=get_agent_compaction_summary_system_text_v1(),
        task_type=task_type,
        owner_type=owner_type,
        owner_id=owner_id,
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        max_prompt_tokens=summarizer_budget,
        on_text_delta=None,
    )
