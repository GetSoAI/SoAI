"""SoAI - MCP read_file text response budget [backend/mcp/tools/file_text_response_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_prompt_safe_line_payload",)

_MAX_SERIALIZED_RESPONSE_CHARS: int = 20_000


def _format_numbered_lines(lines: list[str], *, start_line_number: int) -> str:
    return "\n".join(f"{start_line_number + index}: {line}" for index, line in enumerate(lines))


def _format_raw_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _render_lines(lines: list[str], *, render: str, start_line: int) -> str:
    if render == "raw":
        return _format_raw_lines(lines)
    return _format_numbered_lines(lines, start_line_number=start_line)


def _build_line_payload(
    *,
    path: str,
    mode: str,
    offset: int,
    limit: int,
    total_lines: int,
    selected: list[str],
    start_line: int | None,
    render: str,
    line_limit_truncated: bool,
    truncation_reason: str | None,
    content_truncated: bool,
    indentation: JSONDict | None,
) -> JSONDict:
    returned_lines = len(selected)
    end_line = (
        None if start_line is None or returned_lines == 0 else start_line + returned_lines - 1
    )
    if returned_lines == 0 or end_line is None:
        next_offset = None
    elif (mode == "slice" and end_line < total_lines) or (
        line_limit_truncated and end_line < total_lines
    ):
        next_offset = end_line + 1
    else:
        next_offset = None
    payload: JSONDict = {
        "path": path,
        "mode": mode,
        "offset": offset,
        "limit": limit,
        "total_lines": total_lines,
        "returned_lines": returned_lines,
        "start_line": start_line,
        "end_line": end_line,
        "next_offset": next_offset,
        "truncated": line_limit_truncated or next_offset is not None or content_truncated,
        "truncation_reason": truncation_reason,
        "content_truncated": content_truncated,
        "max_serialized_response_chars": _MAX_SERIALIZED_RESPONSE_CHARS,
        "serialized_response_chars": 0,
        "content": _render_lines(selected, render=render, start_line=start_line or offset),
    }
    if indentation is not None:
        payload["indentation"] = indentation
    payload["serialized_response_chars"] = len(
        serialize_json_compact_stable_strict(payload, ensure_ascii=False),
    )
    return payload


def _payload_exceeds_budget(payload: JSONDict) -> bool:
    serialized_chars = payload.get("serialized_response_chars")
    return isinstance(serialized_chars, int) and serialized_chars > _MAX_SERIALIZED_RESPONSE_CHARS


def build_prompt_safe_line_payload(
    *,
    path: str,
    mode: str,
    offset: int,
    limit: int,
    total_lines: int,
    selected: list[str],
    start_line: int | None,
    render: str,
    line_limit_truncated: bool,
    indentation: JSONDict | None,
) -> JSONDict:
    candidate = list(selected)
    reason = "line_limit" if line_limit_truncated else None
    payload = _build_line_payload(
        path=path,
        mode=mode,
        offset=offset,
        limit=limit,
        total_lines=total_lines,
        selected=candidate,
        start_line=start_line,
        render=render,
        line_limit_truncated=line_limit_truncated,
        truncation_reason=reason,
        content_truncated=False,
        indentation=indentation,
    )
    while _payload_exceeds_budget(payload) and len(candidate) > 1:
        candidate = candidate[:-1]
        payload = _build_line_payload(
            path=path,
            mode=mode,
            offset=offset,
            limit=limit,
            total_lines=total_lines,
            selected=candidate,
            start_line=start_line,
            render=render,
            line_limit_truncated=True,
            truncation_reason="serialized_size",
            content_truncated=False,
            indentation=indentation,
        )
    if not _payload_exceeds_budget(payload) or not candidate:
        return payload
    shortened = str(candidate[0])
    while shortened and _payload_exceeds_budget(payload):
        shortened = shortened[: max(0, len(shortened) // 2)]
        payload = _build_line_payload(
            path=path,
            mode=mode,
            offset=offset,
            limit=limit,
            total_lines=total_lines,
            selected=[shortened],
            start_line=start_line,
            render=render,
            line_limit_truncated=True,
            truncation_reason="serialized_size",
            content_truncated=True,
            indentation=indentation,
        )
    return payload
