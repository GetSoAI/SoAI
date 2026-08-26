"""SoAI - Assistant timeline terminal tool-call payload inputs [backend/features/assistant_timeline/tool_call_terminal_payload_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.tool_output_limits import append_capped_tool_output

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "merge_latest_result_into_existing_tool",
    "resolve_pending_terminal_tool_output",
)


def merge_latest_result_into_existing_tool(
    *,
    existing: JSONDict | None,
    latest_payload: JSONDict | None,
) -> JSONDict | None:
    if latest_payload is None:
        return existing
    latest_result = latest_payload.get("result")
    if latest_result is None:
        return existing
    if existing is None:
        return {"result": latest_result}
    existing_result = existing.get("result")
    if existing_result is None:
        merged = dict(existing)
        merged["result"] = latest_result
        return merged
    if isinstance(existing_result, dict) and isinstance(latest_result, dict):
        latest_output = latest_result.get("output")
        if "output" not in existing_result and isinstance(latest_output, str):
            merged_result = dict(existing_result)
            merged_result["output"] = latest_output
            merged = dict(existing)
            merged["result"] = merged_result
            return merged
    return existing


def resolve_pending_terminal_tool_output(chunks: list[str] | None) -> str | None:
    if not chunks:
        return None
    output = ""
    emitted_output = False
    for chunk in chunks:
        if not isinstance(chunk, str) or not chunk:
            continue
        output = append_capped_tool_output(output, chunk)
        emitted_output = True
    if not emitted_output:
        return None
    return output
