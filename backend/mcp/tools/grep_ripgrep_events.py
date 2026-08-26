"""SoAI - MCP ripgrep --json event parsing for grep_files [backend/mcp/tools/grep_ripgrep_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.system.async_process_spawning import terminate_async_process_nowait
from core.timing.constants import ASYNC_POLL_SLICE_SEC
from core.validation.integers import is_strict_int
from mcp.tools.grep_types import GrepFileMatch, GrepLineHit, GrepRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "consume_json_events",
    "iterate_decoded_lines_with_poll",
    "read_line_with_poll",
)


async def read_line_with_poll(
    stdout: asyncio.StreamReader,
    proc: asyncio.subprocess.Process,
) -> bytes:
    while True:
        try:
            line = await asyncio.wait_for(stdout.readline(), timeout=ASYNC_POLL_SLICE_SEC)
        except TimeoutError:
            if proc.returncode is not None:
                return b""
            continue
        return line


async def iterate_decoded_lines_with_poll(
    stdout: asyncio.StreamReader,
    proc: asyncio.subprocess.Process,
) -> AsyncIterator[str]:
    while True:
        chunk = await read_line_with_poll(stdout, proc)
        if not chunk:
            return
        yield chunk.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")


async def consume_json_events(
    stdout: asyncio.StreamReader,
    proc: asyncio.subprocess.Process,
    request: GrepRequest,
) -> tuple[list[GrepFileMatch], bool]:
    files: list[GrepFileMatch] = []
    current_path: str | None = None
    current_lines: list[GrepLineHit] = []
    current_match_count = 0
    target = request.head_limit + request.offset
    truncated = False
    while True:
        chunk = await read_line_with_poll(stdout, proc)
        if not chunk:
            break
        try:
            event = parse_json_dict(
                chunk.decode("utf-8", errors="replace"),
                field="ripgrep json event",
            )
        except ValidationError:
            continue
        event_type = event.get("type")
        if event_type == "begin":
            current_path = _event_path(event)
            current_lines = []
            current_match_count = 0
            continue
        if event_type in ("match", "context"):
            hit = _line_hit_from_event(event, is_context=event_type == "context")
            if hit is not None:
                current_lines.append(hit)
            if event_type == "match":
                current_match_count += 1
            continue
        if event_type == "end":
            if current_path is not None and (current_match_count > 0 or current_lines):
                files.append(
                    GrepFileMatch(
                        path=current_path,
                        match_count=current_match_count,
                        lines=tuple(current_lines),
                    ),
                )
            current_path = None
            current_lines = []
            current_match_count = 0
            if len(files) >= target:
                truncated = True
                terminate_async_process_nowait(proc)
                break
    return files, truncated


def _event_path(event: JSONDict) -> str | None:
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    path_section = data.get("path")
    if not isinstance(path_section, dict):
        return None
    text_value = path_section.get("text")
    if isinstance(text_value, str) and text_value:
        return text_value
    bytes_value = path_section.get("bytes")
    if isinstance(bytes_value, str) and bytes_value:
        return bytes_value
    return None


def _line_hit_from_event(event: JSONDict, *, is_context: bool) -> GrepLineHit | None:
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    line_number_value: JSONValue = data.get("line_number")
    if not is_strict_int(line_number_value):
        return None
    lines_section = data.get("lines")
    if not isinstance(lines_section, dict):
        return None
    text_value = lines_section.get("text")
    if isinstance(text_value, str):
        text = text_value.rstrip("\n").rstrip("\r")
    else:
        bytes_value = lines_section.get("bytes")
        if not isinstance(bytes_value, str):
            return None
        text = bytes_value.rstrip("\n").rstrip("\r")
    return GrepLineHit(line_number=int(line_number_value), text=text, is_context=is_context)
