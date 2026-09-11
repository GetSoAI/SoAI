"""SoAI - Tool result prompt shaping for agent context [backend/core/tool_calls/tool_result_prompt_shaping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.openai.truncation import build_marker_truncation_text
from core.tool_calls.tool_result_prompt_primitives import (
    MAX_EMERGENCY_PASSES,
    TRUNCATED_KEY,
    ToolResultPromptShapingStats,
    depth_truncation_payload,
    omit_items_payload,
    redaction_payload,
    safe_json_dumps,
)
from core.types.json import JSONDict, JSONValue

__all__ = (
    "ToolResultPromptShapingStats",
    "shape_tool_result_json_for_prompt",
)

LOGGER_NAME = "SoAI.core.tool_calls.tool_result_prompt_shaping"


def _truncate_string(value: str, *, max_chars: int, stats: ToolResultPromptShapingStats) -> str:
    if len(value) <= max_chars:
        return value
    stats.truncated_strings += 1
    return build_marker_truncation_text(original=value, max_total_chars=max_chars)


def _shape_value(
    value: JSONValue,
    *,
    depth: int,
    max_depth: int,
    per_string_cap: int,
    max_items: int,
    max_keys: int,
    stats: ToolResultPromptShapingStats,
) -> JSONValue:
    if depth > max_depth:
        stats.max_depth_truncations += 1
        return depth_truncation_payload()
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _truncate_string(value, max_chars=per_string_cap, stats=stats)
    if isinstance(value, list):
        items = value[:max_items]
        omitted = max(0, len(value) - len(items))
        shaped_list: list[JSONValue] = [
            _shape_value(
                item,
                depth=depth + 1,
                max_depth=max_depth,
                per_string_cap=per_string_cap,
                max_items=max_items,
                max_keys=max_keys,
                stats=stats,
            )
            for item in items
        ]
        if omitted:
            stats.omitted_items += omitted
            shaped_list.append(omit_items_payload(omitted_items=omitted))
        return shaped_list
    if isinstance(value, dict):
        keys = [key for key in value if isinstance(key, str)]
        keys.sort()
        kept_keys = keys[:max_keys]
        omitted = max(0, len(keys) - len(kept_keys))
        shaped_dict: JSONDict = {}
        for key in kept_keys:
            raw_item = value.get(key)
            if key.endswith("_base64"):
                original_text = raw_item if isinstance(raw_item, str) else str(raw_item)
                stats.redacted_binary_base64 += 1
                shaped_dict[key] = redaction_payload(
                    reason=f"{key}_redacted_for_prompt",
                    original_chars=len(original_text),
                )
                continue
            shaped_dict[key] = _shape_value(
                raw_item,
                depth=depth + 1,
                max_depth=max_depth,
                per_string_cap=per_string_cap,
                max_items=max_items,
                max_keys=max_keys,
                stats=stats,
            )
        if omitted:
            stats.omitted_keys += omitted
            shaped_dict[TRUNCATED_KEY] = {"omitted_keys": int(omitted)}
        return shaped_dict
    return _truncate_string(str(value), max_chars=per_string_cap, stats=stats)


def _drop_large_fields(value: JSONValue, stats: ToolResultPromptShapingStats) -> JSONValue:
    if isinstance(value, list):
        return [_drop_large_fields(item, stats) for item in value]
    if not isinstance(value, dict):
        return value
    drop_keys = frozenset(
        {
            "content",
            "snapshot",
            "html",
            "markdown",
            "text",
            "output",
            "stdout",
            "stderr",
            "page_source",
            "body",
            "response",
        },
    )
    shaped: JSONDict = {}
    for key, raw_item in value.items():
        if not isinstance(key, str):
            continue
        if key in drop_keys and raw_item is not None:
            raw_text = raw_item if isinstance(raw_item, str) else safe_json_dumps(raw_item)
            stats.emergency_drops += 1
            shaped[key] = redaction_payload(
                reason="tool_result_field_dropped_for_prompt",
                original_chars=len(raw_text),
            )
            continue
        shaped[key] = _drop_large_fields(raw_item, stats)
    return shaped


def shape_tool_result_json_for_prompt(
    *,
    tool_name: str,
    tool_result: JSONValue,
    max_chars: int,
    max_depth: int,
    max_items: int,
    max_keys: int,
) -> tuple[str, ToolResultPromptShapingStats]:
    resolved_tool_name = str(tool_name or "").strip()
    resolved_max_chars = max(1000, int(max_chars))
    per_string_cap = max(64, min(resolved_max_chars, int(resolved_max_chars * 0.9)))
    current_max_items = max(1, int(max_items))
    current_max_keys = max(1, int(max_keys))
    current_max_depth = max(1, int(max_depth))
    stats = ToolResultPromptShapingStats(
        tool_name=resolved_tool_name or "unknown",
        original_chars=len(safe_json_dumps(tool_result)),
        shaped_chars=0,
    )
    logger = get_logger(LOGGER_NAME)
    attempt = 0
    while attempt < MAX_EMERGENCY_PASSES:
        attempt += 1
        if attempt >= 7:
            per_string_cap = min(int(per_string_cap), 256)
            current_max_items = min(int(current_max_items), 25)
            current_max_keys = min(int(current_max_keys), 75)
            current_max_depth = min(int(current_max_depth), 4)
        if attempt >= 8:
            per_string_cap = min(int(per_string_cap), 128)
            current_max_items = min(int(current_max_items), 5)
            current_max_keys = min(int(current_max_keys), 30)
            current_max_depth = min(int(current_max_depth), 3)
        stats.redacted_binary_base64 = 0
        stats.truncated_strings = 0
        stats.omitted_keys = 0
        stats.omitted_items = 0
        stats.max_depth_truncations = 0
        stats.emergency_drops = 0
        shaped_value = _shape_value(
            tool_result,
            depth=0,
            max_depth=int(current_max_depth),
            per_string_cap=int(per_string_cap),
            max_items=int(current_max_items),
            max_keys=int(current_max_keys),
            stats=stats,
        )
        shaped_json = safe_json_dumps(shaped_value)
        shaped_len = len(shaped_json)
        if shaped_len <= resolved_max_chars:
            stats.shaped_chars = len(shaped_json)
            if stats.changed:
                logger.trace(
                    "Shaped tool result for prompt (tool=%s, original_chars=%s, shaped_chars=%s, redacted_binary_base64=%s, truncated_strings=%s, omitted_keys=%s, omitted_items=%s, max_depth=%s, emergency_drops=%s).",
                    stats.tool_name,
                    stats.original_chars,
                    len(shaped_json),
                    stats.redacted_binary_base64,
                    stats.truncated_strings,
                    stats.omitted_keys,
                    stats.omitted_items,
                    stats.max_depth_truncations,
                    stats.emergency_drops,
                )
            return shaped_json, stats
        if attempt >= 3:
            reduced = _drop_large_fields(shaped_value, stats)
            reduced_json = safe_json_dumps(reduced)
            if len(reduced_json) <= resolved_max_chars:
                stats.shaped_chars = len(reduced_json)
                logger.warning(
                    "Shaped tool result for prompt after field drops (tool=%s, original_chars=%s, shaped_chars=%s, emergency_drops=%s).",
                    stats.tool_name,
                    stats.original_chars,
                    len(reduced_json),
                    stats.emergency_drops,
                )
                return reduced_json, stats
        ratio = float(shaped_len) / float(resolved_max_chars)
        scale = min(0.75, 1.0 / max(1.0, ratio))
        per_string_cap = max(64, int(per_string_cap * scale))
        if current_max_items > 1:
            current_max_items = max(1, int(current_max_items * scale))
        if current_max_keys > 1:
            current_max_keys = max(1, int(current_max_keys * scale))
        if attempt >= 4 and current_max_depth > 1:
            current_max_depth = max(1, int(current_max_depth) - 1)
    stub_payload: JSONDict = {
        TRUNCATED_KEY: {
            "reason": "tool_result_too_large_for_prompt",
            "tool": stats.tool_name,
            "original_chars": stats.original_chars,
        },
    }
    stub_json = safe_json_dumps(stub_payload)
    stats.shaped_chars = len(stub_json)
    logger.warning(
        "Tool result exceeded prompt shaping budget; replaced with stub (tool=%s, original_chars=%s, shaped_chars=%s).",
        stats.tool_name,
        stats.original_chars,
        stats.shaped_chars,
    )
    return stub_json, stats
