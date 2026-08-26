"""SoAI - MCP ripgrep count mode for grep_files [backend/mcp/tools/grep_ripgrep_run_count.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.tools.grep_ripgrep_arguments import (
    build_base_ripgrep_args,
    resolve_search_target,
)
from mcp.tools.grep_ripgrep_events import iterate_decoded_lines_with_poll
from mcp.tools.grep_ripgrep_process import (
    drain_process_uninterruptible,
    raise_for_returncode,
    read_stderr,
    spawn_ripgrep_process,
    terminate_process,
)
from mcp.tools.grep_types import GrepFileMatch, GrepRequest, GrepResult

__all__ = ("run_count",)


async def run_count(binary_path: str, request: GrepRequest) -> GrepResult:
    args = build_base_ripgrep_args(binary_path, request)
    args.extend(["-c", "--null", "--with-filename"])
    args.append(request.pattern)
    args.append(resolve_search_target(request))
    proc, stdout = await spawn_ripgrep_process(args)
    entries: list[tuple[str, int]] = []
    seen: set[str] = set()
    target = request.head_limit + request.offset
    truncated = False
    try:
        async for text in iterate_decoded_lines_with_poll(stdout, proc):
            separator_index = text.find("\0")
            if separator_index <= 0:
                continue
            path = text[:separator_index]
            count_str = text[separator_index + 1 :]
            if not count_str.isdigit():
                continue
            if path in seen:
                continue
            seen.add(path)
            entries.append((path, int(count_str)))
            if len(entries) >= target:
                truncated = True
                terminate_process(proc)
                break
    finally:
        terminated = truncated
        await drain_process_uninterruptible(proc, terminated=terminated)
    stderr_output = await read_stderr(proc)
    raise_for_returncode(proc, truncated=truncated, stderr_text=stderr_output)
    entries.sort(key=lambda item: item[0])
    sliced = entries[request.offset : request.offset + request.head_limit]
    files = tuple(GrepFileMatch(path=path, match_count=count, lines=()) for path, count in sliced)
    return GrepResult(
        files=files,
        truncated=truncated,
        total_matches=sum(count for _, count in sliced),
        truncated_reason="head_limit" if truncated else None,
    )
