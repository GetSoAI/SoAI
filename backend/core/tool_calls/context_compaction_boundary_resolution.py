"""SoAI - Resilient context compaction boundary resolution [backend/core/tool_calls/context_compaction_boundary_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.tool_calls.context_compaction_boundary_state import (
    context_compaction_boundary_matches,
)
from core.tool_calls.context_compaction_markers import (
    extract_context_compaction_marker_from_message,
    is_context_compaction_active_completed_marker,
    is_context_compaction_removed_marker,
)
from core.tool_calls.context_compaction_prompt_message import (
    normalize_context_compaction_prompt_message,
)
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.types.json import JSONDict

__all__ = (
    "ContextCompactionBoundaryResolution",
    "InactiveContextCompactionBoundary",
    "resolve_context_compaction_boundaries",
    "resolve_context_compaction_boundaries_from_markers",
)


@dataclass(frozen=True, slots=True)
class InactiveContextCompactionBoundary:
    message_index: int
    tool_call_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ContextCompactionBoundaryResolution:
    messages: list[JSONDict]
    active_message_index: int | None
    active_tool_call_id: str | None
    inactive_boundaries: tuple[InactiveContextCompactionBoundary, ...] = field(
        default_factory=tuple,
    )


@dataclass(frozen=True, slots=True)
class _PreparedCompactionMessage:
    message: JSONDict
    marker: JSONDict | None


def _resolve_marker_tool_call_id(marker: JSONDict) -> str | None:
    for field_name in ("tool_call_id", "call_id"):
        value = marker.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_completed_marker(marker: JSONDict | None) -> JSONDict | None:
    if marker is None:
        return None
    if not is_context_compaction_active_completed_marker(marker):
        return None
    return marker


def _prepare_messages(
    source_messages: Sequence[JSONDict],
    markers: Sequence[JSONDict | None],
) -> list[_PreparedCompactionMessage]:
    if len(source_messages) != len(markers):
        raise ValidationError("Context compaction marker count must match the message count.")
    prepared_messages: list[_PreparedCompactionMessage] = []
    for source_message, marker in zip(source_messages, markers, strict=True):
        message = dict(source_message)
        prepared_messages.append(_PreparedCompactionMessage(message=message, marker=marker))
    return prepared_messages


def _strip_context_compaction_activity_messages(
    messages: Sequence[_PreparedCompactionMessage],
) -> list[JSONDict]:
    return [dict(prepared.message) for prepared in messages if prepared.marker is None]


def _build_inactive_boundary(
    *,
    message_index: int,
    marker: JSONDict | None,
    reason: str,
) -> InactiveContextCompactionBoundary:
    return InactiveContextCompactionBoundary(
        message_index=int(message_index),
        tool_call_id=(_resolve_marker_tool_call_id(marker) if marker is not None else None),
        reason=str(reason),
    )


def _resolve_prepared_context_compaction_boundaries(
    message_body: Sequence[_PreparedCompactionMessage],
    *,
    pinned_prefix: Sequence[_PreparedCompactionMessage],
    cached_resolutions: dict[int, ContextCompactionBoundaryResolution],
) -> ContextCompactionBoundaryResolution:
    message_count = len(message_body)
    if not pinned_prefix:
        cached_resolution = cached_resolutions.get(message_count)
        if cached_resolution is not None:
            return cached_resolution
    inactive: list[InactiveContextCompactionBoundary] = []
    for boundary_index in range(message_count - 1, -1, -1):
        boundary_message = message_body[boundary_index]
        marker = _resolve_completed_marker(boundary_message.marker)
        if marker is None:
            if boundary_message.marker is not None:
                inactive.append(
                    _build_inactive_boundary(
                        message_index=boundary_index,
                        marker=boundary_message.marker,
                        reason=(
                            "removed"
                            if is_context_compaction_removed_marker(boundary_message.marker)
                            else "non_terminal"
                        ),
                    ),
                )
            continue
        details = coerce_json_dict(marker.get("details"))
        if details is None:
            inactive.append(
                _build_inactive_boundary(
                    message_index=boundary_index,
                    marker=marker,
                    reason="invalid_details",
                ),
            )
            continue
        prompt_message = normalize_context_compaction_prompt_message(
            marker.get("prompt_message"),
        )
        if prompt_message is None:
            inactive.append(
                _build_inactive_boundary(
                    message_index=boundary_index,
                    marker=marker,
                    reason="invalid_prompt_message",
                ),
            )
            continue
        try:
            prefix_resolution = _resolve_prepared_context_compaction_boundaries(
                message_body[:boundary_index],
                pinned_prefix=[],
                cached_resolutions=cached_resolutions,
            )
            boundary_matches = context_compaction_boundary_matches(
                prefix_resolution.messages,
                details,
                strip_leading_pinned_prefix=False,
            )
        except ValidationError:
            boundary_matches = False
            prefix_resolution = ContextCompactionBoundaryResolution(
                messages=_strip_context_compaction_activity_messages(message_body[:boundary_index]),
                active_message_index=None,
                active_tool_call_id=None,
            )
        if not boundary_matches:
            inactive.append(
                _build_inactive_boundary(
                    message_index=boundary_index,
                    marker=marker,
                    reason="digest_mismatch",
                ),
            )
            continue
        messages = [dict(prepared.message) for prepared in pinned_prefix]
        messages.append(prompt_message)
        messages.extend(
            dict(prepared.message)
            for prepared in message_body[boundary_index + 1 :]
            if prepared.marker is None
        )
        resolution = ContextCompactionBoundaryResolution(
            messages=messages,
            active_message_index=boundary_index,
            active_tool_call_id=_resolve_marker_tool_call_id(marker),
            inactive_boundaries=(
                *prefix_resolution.inactive_boundaries,
                *tuple(reversed(inactive)),
            ),
        )
        if not pinned_prefix:
            cached_resolutions[message_count] = resolution
        return resolution
    resolution = ContextCompactionBoundaryResolution(
        messages=[
            *[dict(prepared.message) for prepared in pinned_prefix],
            *_strip_context_compaction_activity_messages(message_body),
        ],
        active_message_index=None,
        active_tool_call_id=None,
        inactive_boundaries=tuple(reversed(inactive)),
    )
    if not pinned_prefix:
        cached_resolutions[message_count] = resolution
    return resolution


def resolve_context_compaction_boundaries(
    source_messages: Sequence[JSONDict],
    *,
    strip_leading_pinned_prefix: bool,
) -> ContextCompactionBoundaryResolution:
    markers = [
        (
            extract_context_compaction_marker_from_message(message)
            if message.get("role") == "assistant"
            else None
        )
        for message in source_messages
    ]
    return resolve_context_compaction_boundaries_from_markers(
        source_messages,
        markers,
        strip_leading_pinned_prefix=strip_leading_pinned_prefix,
    )


def resolve_context_compaction_boundaries_from_markers(
    source_messages: Sequence[JSONDict],
    markers: Sequence[JSONDict | None],
    *,
    strip_leading_pinned_prefix: bool,
) -> ContextCompactionBoundaryResolution:
    prepared_messages = _prepare_messages(source_messages, markers)
    pinned_prefix: Sequence[_PreparedCompactionMessage] = []
    message_body: Sequence[_PreparedCompactionMessage] = prepared_messages
    if strip_leading_pinned_prefix:
        pinned_messages, _ = split_leading_pinned_prefix(
            [prepared.message for prepared in prepared_messages],
        )
        pinned_count = len(pinned_messages)
        pinned_prefix = prepared_messages[:pinned_count]
        message_body = prepared_messages[pinned_count:]
    return _resolve_prepared_context_compaction_boundaries(
        message_body,
        pinned_prefix=pinned_prefix,
        cached_resolutions={},
    )
