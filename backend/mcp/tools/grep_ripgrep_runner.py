"""SoAI - MCP grep_files ripgrep runner [backend/mcp/tools/grep_ripgrep_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.grep_ripgrep_arguments import (
    build_base_ripgrep_args,
    resolve_search_target,
)
from mcp.tools.grep_ripgrep_binary import resolve_ripgrep_binary
from mcp.tools.grep_ripgrep_events import iterate_decoded_lines_with_poll
from mcp.tools.grep_ripgrep_process import (
    drain_process_uninterruptible,
    raise_for_returncode,
    read_stderr,
    spawn_ripgrep_process,
    terminate_process,
)
from mcp.tools.grep_ripgrep_run_content import run_content
from mcp.tools.grep_ripgrep_run_count import run_count
from mcp.tools.grep_types import GrepFileMatch, GrepRequest, GrepResult

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("run_ripgrep",)


async def run_ripgrep(runtime_flags: RuntimeFlagsViewProtocol, request: GrepRequest) -> GrepResult:
    binary_path = await resolve_ripgrep_binary(runtime_flags)
    if request.output_mode == "files_with_matches":
        return await _run_files_with_matches(binary_path, request)
    if request.output_mode == "count":
        return await run_count(binary_path, request)
    return await run_content(binary_path, request)


async def _run_files_with_matches(binary_path: str, request: GrepRequest) -> GrepResult:
    args = build_base_ripgrep_args(binary_path, request)
    args.append("--files-with-matches")
    args.append(request.pattern)
    args.append(resolve_search_target(request))
    proc, stdout = await spawn_ripgrep_process(args)
    collected: list[str] = []
    seen: set[str] = set()
    target = request.head_limit + request.offset
    truncated = False
    try:
        async for line in iterate_decoded_lines_with_poll(stdout, proc):
            path = line.strip()
            if not path or path in seen:
                continue
            seen.add(path)
            collected.append(path)
            if request.offset == 0 and len(collected) >= target:
                truncated = True
                terminate_process(proc)
                break
    finally:
        await drain_process_uninterruptible(proc, terminated=truncated)
    stderr_text = await read_stderr(proc)
    raise_for_returncode(proc, truncated=truncated, stderr_text=stderr_text)
    collected.sort()
    sliced = collected[request.offset : request.offset + request.head_limit]
    return GrepResult(
        files=tuple(GrepFileMatch(path=path, match_count=0, lines=()) for path in sliced),
        truncated=truncated,
        total_matches=0,
        truncated_reason="head_limit" if truncated else None,
    )
