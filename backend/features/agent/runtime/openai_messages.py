"""SoAI - Agent OpenAI message assembly [backend/features/agent/runtime/openai_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mode import normalize_agent_mode
from core.openai.tool_call_arguments import (
    serialize_openai_tool_call_arguments_for_prompt,
    should_sanitize_openai_tool_call_arguments,
)
from core.openai.truncation import build_marker_truncation_text
from core.tool_calls.error_payloads import TOOL_CALL_USER_DENIED_ERROR_CODE
from core.tool_calls.status_values import is_failure_tool_call_status
from core.tool_calls.tool_result_omission import build_tool_result_omission_stub_json
from core.tool_calls.tool_result_prompt_primitives import (
    safe_json_dumps,
)
from features.agent.runtime.tool_call_execution_support import (
    resolve_tool_completion_status,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_assistant_tool_message",
    "build_post_tool_prompt_messages",
)


def build_assistant_tool_message(tool_calls: list[JSONDict], content: str) -> JSONDict:
    resolved_content = content.strip()
    tool_call_payloads: list[JSONDict] = []
    for tool_call in tool_calls:
        tool_call_id = str(tool_call.get("id") or "").strip()
        tool_name = str(tool_call.get("name") or "").strip()
        arguments_text = serialize_openai_tool_call_arguments_for_prompt(tool_call.get("arguments"))
        tool_call_payloads.append(
            {
                "id": tool_call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": arguments_text},
            },
        )
    return {
        "role": "assistant",
        "content": resolved_content,
        "tool_calls": tool_call_payloads,
    }


def _truncate_text(value: str, *, max_chars: int) -> str:
    normalized = str(value or "")
    if max_chars <= 0:
        return ""
    return build_marker_truncation_text(original=normalized, max_total_chars=max_chars)


def _coerce_failure_field_text(value: JSONValue | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return safe_json_dumps(value).strip()


def _is_execute_mode(settings: AgentSettings) -> bool:
    return normalize_agent_mode(settings.mode, strict=False) == "execute"


def build_post_tool_prompt_messages(
    *,
    tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    assistant_text: str | None,
    settings: AgentSettings,
    shape_cache: ToolResultPromptShapeCache,
) -> list[JSONDict]:
    resolved_assistant_text = assistant_text.strip() if assistant_text is not None else ""
    pairs: list[tuple[JSONDict, JSONValue]] = []
    for tool_call, tool_result in zip(tool_calls, tool_results, strict=False):
        if not isinstance(tool_call, dict):
            continue
        pairs.append((dict(tool_call), tool_result))
    if len(tool_calls) > len(tool_results):
        missing_count = len(tool_calls) - len(tool_results)
        for tool_call in tool_calls[-missing_count:]:
            if not isinstance(tool_call, dict):
                continue
            pairs.append(
                (
                    dict(tool_call),
                    {
                        "error": "Tool call completed without a result payload.",
                        "code": "server_error",
                    },
                ),
            )
    if not pairs:
        if resolved_assistant_text:
            return [{"role": "assistant", "content": resolved_assistant_text}]
        return []
    all_calls = [tool_call for tool_call, _ in pairs]
    messages: list[JSONDict] = [build_assistant_tool_message(all_calls, resolved_assistant_text)]
    max_total_chars_per_tool_block = int(settings.tool_result_prompt_max_total_chars_per_tool_block)
    remaining_tool_result_chars = max(0, int(max_total_chars_per_tool_block))
    tool_result_budget_exhausted = False
    for tool_call, tool_result in pairs:
        tool_call_id = str(tool_call.get("id") or "").strip()
        tool_name = str(tool_call.get("name") or "").strip()
        if tool_result_budget_exhausted or remaining_tool_result_chars <= 0:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": build_tool_result_omission_stub_json(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                    ),
                },
            )
            tool_result_budget_exhausted = True
            continue
        if not is_failure_tool_call_status(resolve_tool_completion_status(tool_result)):
            shaped_json = shape_cache.shape(
                tool_name=tool_name,
                tool_result=tool_result,
                max_chars=settings.tool_result_prompt_max_chars,
                max_depth=settings.tool_result_prompt_max_depth,
                max_items=settings.tool_result_prompt_max_items,
                max_keys=settings.tool_result_prompt_max_keys,
            )
            if len(shaped_json) > remaining_tool_result_chars:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": build_tool_result_omission_stub_json(
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                        ),
                    },
                )
                tool_result_budget_exhausted = True
                continue
            remaining_tool_result_chars -= len(shaped_json)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": shaped_json,
                },
            )
            continue
        error_text = (
            _coerce_failure_field_text(tool_result.get("error"))
            if isinstance(tool_result, dict)
            else ""
        ) or "Tool call failed."
        code_text = (
            _coerce_failure_field_text(tool_result.get("code"))
            if isinstance(tool_result, dict)
            else ""
        )
        normalized_code = code_text.strip().lower()
        needs_retry_guidance = False
        if should_sanitize_openai_tool_call_arguments(tool_call.get("arguments")):
            needs_retry_guidance = True
        if (
            isinstance(tool_result, dict)
            and str(tool_result.get("code") or "").strip() == "invalid_tool_arguments_json"
        ):
            needs_retry_guidance = True
        content = (
            _truncate_text(f"error (code={code_text}): {error_text}", max_chars=2000)
            if code_text
            else _truncate_text(f"error: {error_text}", max_chars=2000)
        )
        if needs_retry_guidance:
            target = tool_name or "the tool"
            guidance = (
                f"\nFix: Re-emit the {target} tool call with function.arguments as a JSON object. "
                "Use double quotes in JSON strings; do not use \\' in JSON."
            )
            content = _truncate_text(f"{content}{guidance}", max_chars=2000)
        if _is_execute_mode(settings) and normalized_code not in {
            "cancelled",
            TOOL_CALL_USER_DENIED_ERROR_CODE,
        }:
            recovery_guidance = (
                "\nRecovery: This tool-path failure is local. Do not convert it into a blanket "
                "claim that the overall delegated request is impossible. Retry with adjusted "
                "parameters or switch to another supported path."
            )
            content = _truncate_text(f"{content}{recovery_guidance}", max_chars=2000)
        if len(content) > remaining_tool_result_chars:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": build_tool_result_omission_stub_json(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                    ),
                },
            )
            tool_result_budget_exhausted = True
            continue
        remaining_tool_result_chars -= len(content)
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
    return messages
