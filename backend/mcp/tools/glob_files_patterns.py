"""SoAI - MCP glob_files patterns [backend/mcp/tools/glob_files_patterns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "build_normalized_patterns_to_try",
    "expand_brace_patterns",
)


def expand_brace_patterns(pattern: str) -> list[str]:
    start_index: int | None = None
    for index, character in enumerate(pattern):
        if character != "{":
            continue
        if index > 0 and pattern[index - 1] == "\\":
            continue
        start_index = index
        break
    if start_index is None:
        return [pattern]

    depth = 0
    end_index: int | None = None
    for index in range(start_index, len(pattern)):
        character = pattern[index]
        if character == "{" and not (index > 0 and pattern[index - 1] == "\\"):
            depth += 1
            continue
        if character == "}" and not (index > 0 and pattern[index - 1] == "\\"):
            depth -= 1
            if depth == 0:
                end_index = index
                break
            continue
    if end_index is None:
        return [pattern]

    prefix = pattern[:start_index]
    suffix = pattern[end_index + 1 :]
    brace_body = pattern[start_index + 1 : end_index]

    options: list[str] = []
    token_start = 0
    nested_depth = 0
    for index, character in enumerate(brace_body):
        if character == "{" and not (index > 0 and brace_body[index - 1] == "\\"):
            nested_depth += 1
            continue
        if character == "}" and not (index > 0 and brace_body[index - 1] == "\\"):
            nested_depth = max(0, nested_depth - 1)
            continue
        if (
            character == ","
            and nested_depth == 0
            and not (index > 0 and brace_body[index - 1] == "\\")
        ):
            options.append(brace_body[token_start:index])
            token_start = index + 1
    options.append(brace_body[token_start:])

    expanded: list[str] = []
    for option in options:
        for expanded_option in expand_brace_patterns(option):
            for expanded_suffix in expand_brace_patterns(suffix):
                expanded.append(f"{prefix}{expanded_option}{expanded_suffix}")
    return expanded


def build_normalized_patterns_to_try(raw_pattern: str) -> list[str]:
    raw_patterns_to_try = expand_brace_patterns(raw_pattern)
    patterns_to_try: list[str] = []
    seen: set[str] = set()
    for candidate in raw_patterns_to_try:
        if candidate not in seen:
            patterns_to_try.append(candidate)
            seen.add(candidate)
        if candidate.startswith("./"):
            stripped = candidate[2:]
            if stripped and stripped not in seen:
                patterns_to_try.append(stripped)
                seen.add(stripped)
        if candidate.startswith("**/"):
            stripped = candidate[3:]
            if stripped and stripped not in seen:
                patterns_to_try.append(stripped)
                seen.add(stripped)
    return patterns_to_try
