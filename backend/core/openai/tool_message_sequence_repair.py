"""SoAI - OpenAI tool message sequence repair for internal contracts [backend/core/openai/tool_message_sequence_repair.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.chat_messages_contracts import extract_valid_tool_call_ids
from core.types.json import JSONDict

__all__ = ("repair_openai_tool_message_sequence_for_internal_contracts",)


def repair_openai_tool_message_sequence_for_internal_contracts(
    *,
    messages: list[JSONDict],
) -> tuple[list[JSONDict], bool]:
    repaired: list[JSONDict] = []
    changed = False
    active_tool_block_open = False
    active_expected_tool_call_ids: tuple[str, ...] = ()
    active_expected_tool_call_ids_set: set[str] = set()
    active_satisfied_tool_call_ids: set[str] = set()
    active_assistant_index: int | None = None
    active_tool_results_start_index: int | None = None

    def close_incomplete_tool_block() -> None:
        nonlocal active_tool_block_open
        nonlocal active_expected_tool_call_ids
        nonlocal active_expected_tool_call_ids_set
        nonlocal active_satisfied_tool_call_ids
        nonlocal active_assistant_index
        nonlocal active_tool_results_start_index
        nonlocal repaired
        nonlocal changed

        if not active_tool_block_open:
            return
        if active_assistant_index is not None and 0 <= active_assistant_index < len(repaired):
            assistant_message = dict(repaired[active_assistant_index])
            if "tool_calls" in assistant_message:
                assistant_message.pop("tool_calls", None)
                repaired[active_assistant_index] = assistant_message
                changed = True
        if active_tool_results_start_index is not None:
            start = max(0, int(active_tool_results_start_index))
            if start < len(repaired):
                repaired = list(repaired[:start])
                changed = True
        active_tool_block_open = False
        active_expected_tool_call_ids = ()
        active_expected_tool_call_ids_set = set()
        active_satisfied_tool_call_ids = set()
        active_assistant_index = None
        active_tool_results_start_index = None

    for message in messages:
        if not isinstance(message, dict):
            changed = True
            continue
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role == "tool":
            if not active_tool_block_open:
                changed = True
                continue
            tool_call_id_value = message.get("tool_call_id")
            tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
            if not tool_call_id:
                changed = True
                continue
            if tool_call_id not in active_expected_tool_call_ids_set:
                changed = True
                continue
            if tool_call_id in active_satisfied_tool_call_ids:
                changed = True
                continue
            repaired.append(dict(message))
            active_satisfied_tool_call_ids.add(tool_call_id)
            if len(active_satisfied_tool_call_ids) == len(active_expected_tool_call_ids):
                active_tool_block_open = False
                active_expected_tool_call_ids = ()
                active_expected_tool_call_ids_set = set()
                active_satisfied_tool_call_ids = set()
                active_assistant_index = None
                active_tool_results_start_index = None
            continue

        if active_tool_block_open:
            close_incomplete_tool_block()

        normalized = dict(message)
        if role == "assistant":
            expected_ids = extract_valid_tool_call_ids(normalized.get("tool_calls"))
            repaired.append(normalized)
            tool_calls_value = normalized.get("tool_calls")
            if isinstance(tool_calls_value, list) and tool_calls_value and not expected_ids:
                stripped = dict(normalized)
                stripped.pop("tool_calls", None)
                repaired[-1] = stripped
                changed = True
                continue
            if expected_ids:
                active_tool_block_open = True
                active_expected_tool_call_ids = expected_ids
                active_expected_tool_call_ids_set = set(expected_ids)
                active_satisfied_tool_call_ids = set()
                active_assistant_index = len(repaired) - 1
                active_tool_results_start_index = len(repaired)
            continue
        repaired.append(normalized)

    if active_tool_block_open:
        close_incomplete_tool_block()
    if not changed and len(repaired) != len(messages):
        changed = True
    return repaired, changed
