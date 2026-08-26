"""SoAI - Files-root tool digests: mutations [backend/features/agent/runtime/context_compaction/tool_digests_workspace_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.context_compaction.tool_digests_workspace_formatting import (
    TruncateLineProtocol,
    coerce_bool,
    coerce_int,
    digest_code_diffs,
    summarize_paths,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("digest_workspace_mutation_tool_exchange",)


def digest_workspace_mutation_tool_exchange(
    tool_name: str,
    _tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str] | None:
    if tool_name == "apply_patch":
        patch_parts: list[str] = []
        for key in ["added", "updated", "deleted", "moved"]:
            value = tool_result.get(key)
            if isinstance(value, list):
                patch_parts.append(
                    summarize_paths(
                        [str(item) for item in value if str(item)],
                        label=key,
                        sample=10,
                        truncate_line=truncate_line,
                    ),
                )
                continue
            if is_strict_int(value):
                patch_parts.append(f"{key}={value}")
        patch_parts.extend(digest_code_diffs(tool_result, truncate_line=truncate_line))
        return [f"apply_patch: {'; '.join(patch_parts)}"] if patch_parts else []

    if tool_name == "write_file":
        file_path = coerce_optional_trimmed_str(tool_result.get("path"))
        byte_count = coerce_int(tool_result.get("bytes"))
        existed_before = coerce_bool(tool_result.get("existed_before"))
        changed = coerce_bool(tool_result.get("changed"))
        committed = coerce_bool(tool_result.get("committed"))
        dry_run = coerce_bool(tool_result.get("dry_run"))
        write_parts: list[str] = []
        if file_path:
            write_parts.append(f"path={truncate_line(file_path, max_chars=120)}")
        if byte_count is not None:
            write_parts.append(f"bytes={byte_count}")
        if existed_before is not None:
            write_parts.append(f"existed_before={'yes' if existed_before else 'no'}")
        if changed is not None:
            write_parts.append(f"changed={'yes' if changed else 'no'}")
        if committed is not None:
            write_parts.append(f"committed={'yes' if committed else 'no'}")
        if dry_run is not None:
            write_parts.append(f"dry_run={'yes' if dry_run else 'no'}")
        write_parts.extend(digest_code_diffs(tool_result, truncate_line=truncate_line))
        return [f"write_file: {'; '.join(write_parts)}"] if write_parts else []

    if tool_name == "replace_in_file":
        file_path = coerce_optional_trimmed_str(tool_result.get("path"))
        replacements = coerce_int(tool_result.get("replacements"))
        changed = coerce_bool(tool_result.get("changed"))
        committed = coerce_bool(tool_result.get("committed"))
        dry_run = coerce_bool(tool_result.get("dry_run"))
        replace_parts: list[str] = []
        if file_path:
            replace_parts.append(f"path={truncate_line(file_path, max_chars=120)}")
        if replacements is not None:
            replace_parts.append(f"replacements={replacements}")
        if changed is not None:
            replace_parts.append(f"changed={'yes' if changed else 'no'}")
        if committed is not None:
            replace_parts.append(f"committed={'yes' if committed else 'no'}")
        if dry_run is not None:
            replace_parts.append(f"dry_run={'yes' if dry_run else 'no'}")
        replace_parts.extend(digest_code_diffs(tool_result, truncate_line=truncate_line))
        return [f"replace_in_file: {'; '.join(replace_parts)}"] if replace_parts else []

    return None
