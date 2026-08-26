"""SoAI - MCP ripgrep --json content mode for grep_files [backend/mcp/tools/grep_ripgrep_run_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.tools.grep_ripgrep_arguments import (
    build_base_ripgrep_args,
    resolve_search_target,
)
from mcp.tools.grep_ripgrep_events import consume_json_events
from mcp.tools.grep_ripgrep_process import (
    drain_process_uninterruptible,
    raise_for_returncode,
    read_stderr,
    spawn_ripgrep_process,
)
from mcp.tools.grep_types import GrepRequest, GrepResult

__all__ = ("run_content",)


async def run_content(binary_path: str, request: GrepRequest) -> GrepResult:
    args = build_base_ripgrep_args(binary_path, request)
    args.append("--json")
    if request.multiline:
        args.extend(["-U", "--multiline-dotall"])
    if request.before_context > 0:
        args.extend(["-B", str(request.before_context)])
    if request.after_context > 0:
        args.extend(["-A", str(request.after_context)])
    args.extend(["-m", str(request.max_count_per_file)])
    args.append(request.pattern)
    args.append(resolve_search_target(request))
    proc, stdout = await spawn_ripgrep_process(args)
    truncated = False
    try:
        files, truncated = await consume_json_events(stdout, proc, request)
    finally:
        await drain_process_uninterruptible(proc, terminated=truncated)
    stderr_text = await read_stderr(proc)
    raise_for_returncode(proc, truncated=truncated, stderr_text=stderr_text)
    files.sort(key=lambda entry: entry.path)
    sliced = files[request.offset : request.offset + request.head_limit]
    return GrepResult(
        files=tuple(sliced),
        truncated=truncated,
        total_matches=sum(entry.match_count for entry in sliced),
        truncated_reason="head_limit" if truncated else None,
    )
