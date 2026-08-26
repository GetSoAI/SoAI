"""SoAI - MCP tool name suggestion helpers [backend/core/mcp/tool_name_suggestions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import difflib
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.mcp.qualified_name import (
    decode_qualified_tool_name,
    encode_qualified_tool_name,
    is_valid_qualified_server_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ToolNameCandidate",
    "append_tool_suggestions_to_message",
    "build_tool_name_candidates_from_entry_map",
    "build_tool_name_candidates_from_named_descriptions",
    "build_tool_name_candidates_from_names",
    "build_tool_name_candidates_from_remote_tools",
    "suggest_tool_names",
)

_MAX_SUGGESTIONS = 5
_MIN_SIMILARITY_RATIO = 0.72
_TOKEN_SPLIT_PATTERN = r"[_\-\.\s]+"
_DESCRIPTION_TOKEN_PATTERN = r"[a-z0-9]+"


@dataclass(frozen=True, slots=True)
class ToolNameCandidate:
    name: str
    description: str | None = None


def build_tool_name_candidates_from_names(
    tool_names: Collection[str],
) -> tuple[ToolNameCandidate, ...]:
    candidates: list[ToolNameCandidate] = []
    for tool_name in tool_names:
        normalized_name = str(tool_name or "").strip()
        if not normalized_name:
            continue
        candidates.append(ToolNameCandidate(name=normalized_name))
    return tuple(candidates)


def build_tool_name_candidates_from_named_descriptions(
    named_descriptions: Mapping[str, str | None],
) -> tuple[ToolNameCandidate, ...]:
    candidates: list[ToolNameCandidate] = []
    for tool_name, description in named_descriptions.items():
        normalized_name = str(tool_name or "").strip()
        if not normalized_name:
            continue
        normalized_description = (
            description.strip() if isinstance(description, str) and description.strip() else None
        )
        candidates.append(
            ToolNameCandidate(name=normalized_name, description=normalized_description),
        )
    return tuple(candidates)


def build_tool_name_candidates_from_entry_map(
    entry_map: Mapping[str, Mapping[str, JSONValue]],
) -> tuple[ToolNameCandidate, ...]:
    named_descriptions: dict[str, str | None] = {}
    for tool_name, entry in entry_map.items():
        normalized_name = str(tool_name or "").strip()
        if not normalized_name:
            continue
        named_descriptions[normalized_name] = _resolve_entry_description(entry)
    return build_tool_name_candidates_from_named_descriptions(named_descriptions)


def build_tool_name_candidates_from_remote_tools(
    remote_tools: Collection[Mapping[str, JSONValue]],
) -> tuple[ToolNameCandidate, ...]:
    candidates: list[ToolNameCandidate] = []
    for remote_tool in remote_tools:
        name_value = remote_tool.get("name")
        server_id_value = remote_tool.get("server_id")
        if not isinstance(name_value, str) or not name_value.strip():
            continue
        if not isinstance(server_id_value, str) or not server_id_value.strip():
            continue
        if not is_valid_qualified_server_id(server_id_value.strip()):
            continue
        description_value = remote_tool.get("description")
        description = (
            description_value.strip()
            if isinstance(description_value, str) and description_value.strip()
            else None
        )
        candidates.append(
            ToolNameCandidate(
                name=encode_qualified_tool_name(server_id_value.strip(), name_value.strip()),
                description=description,
            ),
        )
    return tuple(candidates)


def suggest_tool_names(
    requested_name: str,
    candidates: Collection[ToolNameCandidate],
) -> tuple[str, ...]:
    normalized_requested_name = str(requested_name or "").strip()
    if not normalized_requested_name:
        return ()
    requested_server_id, requested_local_name = decode_qualified_tool_name(
        normalized_requested_name,
    )
    requested_comparison_name = (
        requested_local_name if requested_server_id is not None else normalized_requested_name
    )
    requested_tokens = _tokenize_name(requested_comparison_name)
    requested_compact = _compact_name(requested_comparison_name)
    if not requested_tokens and not requested_compact:
        return ()
    candidate_pool = list(candidates)
    if requested_server_id is not None:
        same_server_candidates = [
            candidate
            for candidate in candidate_pool
            if decode_qualified_tool_name(candidate.name)[0] == requested_server_id
        ]
        if same_server_candidates:
            candidate_pool = same_server_candidates
    scored_candidates: list[tuple[bool, int, bool, int, float, str]] = []
    seen_names: set[str] = set()
    for candidate in candidate_pool:
        normalized_candidate_name = str(candidate.name or "").strip()
        if not normalized_candidate_name or normalized_candidate_name in seen_names:
            continue
        seen_names.add(normalized_candidate_name)
        candidate_server_id, candidate_local_name = decode_qualified_tool_name(
            normalized_candidate_name,
        )
        candidate_comparison_name = (
            candidate_local_name if candidate_server_id is not None else normalized_candidate_name
        )
        candidate_tokens = _tokenize_name(candidate_comparison_name)
        candidate_compact = _compact_name(candidate_comparison_name)
        token_overlap = len(requested_tokens.intersection(candidate_tokens))
        prefix_or_substring_match = bool(
            requested_compact
            and candidate_compact
            and (
                requested_compact in candidate_compact
                or candidate_compact.startswith(requested_compact)
                or requested_compact.startswith(candidate_compact)
            ),
        )
        description_overlap = len(
            requested_tokens.intersection(_tokenize_description(candidate.description)),
        )
        similarity_ratio = (
            difflib.SequenceMatcher(a=requested_compact, b=candidate_compact).ratio()
            if requested_compact and candidate_compact
            else 0.0
        )
        exact_match = bool(requested_compact and requested_compact == candidate_compact)
        if not (
            token_overlap > 0
            or prefix_or_substring_match
            or description_overlap > 0
            or similarity_ratio >= _MIN_SIMILARITY_RATIO
        ):
            continue
        scored_candidates.append(
            (
                exact_match,
                token_overlap,
                prefix_or_substring_match,
                description_overlap,
                similarity_ratio,
                normalized_candidate_name,
            ),
        )
    scored_candidates.sort(
        key=lambda item: (-int(item[0]), -item[1], -int(item[2]), -item[3], -item[4], item[5]),
    )
    return tuple(item[5] for item in scored_candidates[:_MAX_SUGGESTIONS])


def append_tool_suggestions_to_message(message: str, suggestions: Collection[str]) -> str:
    normalized_message = str(message or "").strip()
    normalized_suggestions = [
        str(suggestion).strip()
        for suggestion in suggestions
        if isinstance(suggestion, str) and suggestion.strip()
    ]
    if not normalized_suggestions:
        return normalized_message
    rendered_suggestions = ", ".join(normalized_suggestions)
    return f"{normalized_message} Did you mean: {rendered_suggestions}?"


def _resolve_entry_description(entry: Mapping[str, JSONValue]) -> str | None:
    description = _read_string(entry.get("description"))
    if description is not None:
        return description
    definition_value = entry.get("definition")
    if isinstance(definition_value, Mapping):
        definition_description = _read_string(definition_value.get("description"))
        if definition_description is not None:
            return definition_description
        function_value = definition_value.get("function")
        if isinstance(function_value, Mapping):
            function_description = _read_string(function_value.get("description"))
            if function_description is not None:
                return function_description
    raw_value = entry.get("raw")
    if isinstance(raw_value, Mapping):
        raw_description = _read_string(raw_value.get("description"))
        if raw_description is not None:
            return raw_description
    return None


def _read_string(value: JSONValue | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _compact_name(value: str) -> str:
    return "".join(_tokenize_name_parts(value))


def _tokenize_name(value: str) -> frozenset[str]:
    return frozenset(_tokenize_name_parts(value))


def _tokenize_name_parts(value: str) -> tuple[str, ...]:
    normalized_value = str(value or "").strip().lower()
    if not normalized_value:
        return ()
    parts: list[str] = []
    for chunk in normalized_value.split("__"):
        for part in re.split(_TOKEN_SPLIT_PATTERN, chunk):
            normalized_part = _normalize_token(part)
            if normalized_part:
                parts.append(normalized_part)
    return tuple(parts)


def _tokenize_description(value: str | None) -> frozenset[str]:
    if value is None:
        return frozenset()
    tokens: list[str] = []
    for match in re.findall(_DESCRIPTION_TOKEN_PATTERN, value.lower()):
        normalized_token = _normalize_token(match)
        if normalized_token and len(normalized_token) >= 4:
            tokens.append(normalized_token)
    return frozenset(tokens)


def _normalize_token(value: str) -> str:
    stripped_value = value.strip().lower()
    if len(stripped_value) >= 4 and stripped_value.endswith("s"):
        return stripped_value[:-1]
    return stripped_value
