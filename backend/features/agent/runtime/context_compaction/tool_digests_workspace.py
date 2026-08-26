"""SoAI - Files-root tool digests for context compaction [backend/features/agent/runtime/context_compaction/tool_digests_workspace.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.context_compaction.internal_protocols import (
    TruncateLineProtocol,
)
from features.agent.runtime.context_compaction.tool_digests_workspace_formatting import (
    coerce_bool,
    coerce_int,
    summarize_paths,
)
from features.agent.runtime.context_compaction.tool_digests_workspace_mutations import (
    digest_workspace_mutation_tool_exchange,
)
from features.agent.runtime.context_compaction.tool_digests_workspace_reads import (
    digest_workspace_read_tool_exchange,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("digest_workspace_tool_exchange",)


def digest_workspace_tool_exchange(
    tool_name: str,
    tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str] | None:
    error_value = tool_result.get("error")
    if isinstance(error_value, str) and error_value.strip():
        return [f"{tool_name} error: {truncate_line(error_value)}"]

    read_digest = digest_workspace_read_tool_exchange(
        tool_name,
        tool_arguments,
        tool_result,
        truncate_line=truncate_line,
    )
    if read_digest is not None:
        return read_digest

    if tool_name == "grep_files":
        pattern = coerce_optional_trimmed_str(tool_result.get("pattern"))
        include = coerce_optional_trimmed_str(tool_result.get("include"))
        root = coerce_optional_trimmed_str(tool_result.get("path"))
        output_mode = coerce_optional_trimmed_str(tool_result.get("output_mode"))
        truncated = coerce_bool(tool_result.get("truncated"))
        files_value = tool_result.get("files")
        files: list[str] = []
        if isinstance(files_value, list):
            for entry in files_value:
                if not isinstance(entry, dict):
                    continue
                path_value = entry.get("path")
                if not isinstance(path_value, str) or not path_value.strip():
                    continue
                files.append(path_value.strip())
        grep_parts: list[str] = []
        if pattern:
            grep_parts.append(f"pattern={truncate_line(pattern, max_chars=80)}")
        if include:
            grep_parts.append(f"include={truncate_line(include, max_chars=80)}")
        if root:
            grep_parts.append(f"path={truncate_line(root, max_chars=120)}")
        if output_mode:
            grep_parts.append(f"output_mode={output_mode}")
        if truncated is not None:
            grep_parts.append(f"truncated={'yes' if truncated else 'no'}")
        if files:
            grep_parts.append(
                summarize_paths(files, label="files", sample=10, truncate_line=truncate_line),
            )
        return [f"grep_files: {'; '.join(grep_parts)}"] if grep_parts else []

    if tool_name == "glob_files":
        pattern = coerce_optional_trimmed_str(tool_result.get("pattern"))
        root = coerce_optional_trimmed_str(tool_result.get("path"))
        sort = coerce_optional_trimmed_str(tool_result.get("sort"))
        total_matches = coerce_int(tool_result.get("total_matches"))
        truncated = coerce_bool(tool_result.get("truncated"))
        matches_value = tool_result.get("matches")
        matches: list[str] = []
        if isinstance(matches_value, list):
            for path in matches_value:
                if not isinstance(path, str) or not path.strip():
                    continue
                matches.append(path.strip())
        glob_parts: list[str] = []
        if pattern:
            glob_parts.append(f"pattern={truncate_line(pattern, max_chars=80)}")
        if root:
            glob_parts.append(f"path={truncate_line(root, max_chars=120)}")
        if sort:
            glob_parts.append(f"sort={sort}")
        if total_matches is not None:
            glob_parts.append(f"total_matches={total_matches}")
        if truncated is not None:
            glob_parts.append(f"truncated={'yes' if truncated else 'no'}")
        if matches:
            glob_parts.append(
                summarize_paths(matches, label="matches", sample=10, truncate_line=truncate_line),
            )
        return [f"glob_files: {'; '.join(glob_parts)}"] if glob_parts else []

    if tool_name == "list_dir":
        dir_path = coerce_optional_trimmed_str(tool_result.get("path"))
        depth = coerce_int(tool_result.get("depth"))
        truncated = coerce_bool(tool_result.get("truncated"))
        entries_value = tool_result.get("entries")
        entry_paths: list[str] = []
        if isinstance(entries_value, list):
            for entry in entries_value:
                if not isinstance(entry, dict):
                    continue
                path = coerce_optional_trimmed_str(entry.get("path"))
                if path:
                    entry_paths.append(path)
        list_dir_parts: list[str] = []
        if dir_path:
            list_dir_parts.append(f"dir={truncate_line(dir_path, max_chars=120)}")
        if depth is not None:
            list_dir_parts.append(f"depth={depth}")
        if truncated is not None:
            list_dir_parts.append(f"truncated={'yes' if truncated else 'no'}")
        if entry_paths:
            list_dir_parts.append(
                summarize_paths(
                    entry_paths,
                    label="entries",
                    sample=10,
                    truncate_line=truncate_line,
                ),
            )
        return [f"list_dir: {'; '.join(list_dir_parts)}"] if list_dir_parts else []

    if tool_name == "shell":
        cmd = (
            coerce_optional_trimmed_str(tool_arguments.get("cmd"))
            if tool_arguments is not None
            else None
        )
        exit_code = coerce_int(tool_result.get("exit_code"))
        session_id = coerce_int(tool_result.get("session_id"))
        shell_parts: list[str] = []
        if cmd:
            shell_parts.append(f"cmd={truncate_line(cmd, max_chars=160)}")
        if exit_code is not None:
            shell_parts.append(f"exit_code={exit_code}")
        if session_id is not None:
            shell_parts.append(f"session_id={session_id}")
        return [f"shell: {'; '.join(shell_parts)}"] if shell_parts else []

    mutations = digest_workspace_mutation_tool_exchange(
        tool_name,
        tool_arguments,
        tool_result,
        truncate_line=truncate_line,
    )
    if mutations is not None:
        return mutations

    scalar_parts: list[str] = []
    for key in sorted(tool_result.keys()):
        if key in {"snapshot", "screenshot", "image_base64", "html", "markdown"}:
            continue
        value = tool_result.get(key)
        if isinstance(value, bool):
            scalar_parts.append(f"{key}={'true' if value else 'false'}")
            continue
        if is_strict_int(value):
            scalar_parts.append(f"{key}={value}")
            continue
        if isinstance(value, float) and not isinstance(value, bool):
            scalar_parts.append(f"{key}={value}")
            continue
        if isinstance(value, str) and value.strip() and len(value) <= 120:
            scalar_parts.append(f"{key}={truncate_line(value)}")
    if scalar_parts:
        return [f"{tool_name}: {'; '.join(scalar_parts[:4])}"]
    return []
