"""SoAI - Final agent streaming outcome chronology [backend/features/agent/runtime/streaming_inference_outcome_chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.tool_calls.chronology import bound_required_chronology_anchor
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentStreamingInferenceOutcome

__all__ = ("align_outcome_to_final_visible_text",)


def align_outcome_to_final_visible_text(
    outcome: AgentStreamingInferenceOutcome,
    final_text: str,
) -> AgentStreamingInferenceOutcome:
    visible_text_chars = len(final_text)
    if not outcome.tool_calls and outcome.visible_text_chars == visible_text_chars:
        return outcome
    content_upper_bound = outcome.content_index_base + visible_text_chars
    aligned_tool_calls: list[JSONDict] = []
    changed = outcome.visible_text_chars != visible_text_chars
    for tool_call in outcome.tool_calls:
        aligned_tool_call = dict(tool_call)
        content_index_before = aligned_tool_call.get("content_index_before")
        if is_strict_int(content_index_before):
            bounded_content_index_before = bound_required_chronology_anchor(
                content_index_before,
                "content_index_before",
                upper_bound=content_upper_bound,
            )
            if bounded_content_index_before != content_index_before:
                aligned_tool_call["content_index_before"] = bounded_content_index_before
                changed = True
        aligned_tool_calls.append(aligned_tool_call)
    if not changed:
        return outcome
    return replace(
        outcome,
        tool_calls=aligned_tool_calls,
        visible_text_chars=visible_text_chars,
    )
