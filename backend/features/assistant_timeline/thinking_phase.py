"""SoAI - Shared assistant timeline thinking phase mapping [backend/features/assistant_timeline/thinking_phase.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.thinking_preface import (
    resolve_committed_thinking_preface_rendering,
    resolve_thinking_preface_rendering,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_thinking_phase",
    "normalize_thinking_phase_text_for_rendering",
)

_TOOL_CALL_BLOCK_REGEX = r"<tool_call\b[^>]*>.*?</tool_call>"
_THINKING_MARKER_REGEX = r"</?\s*(thinking|think)(\s[^>]*)?>"
_THINKING_MARKER_LINE_REGEX = r"^[ \t]*</?[ \t]*(thinking|think)([ \t][^>]*)?>[ \t]*\r?\n?"


def _strip_tool_call_markup(text: str) -> str:
    if not text:
        return text
    match = re.search(_TOOL_CALL_BLOCK_REGEX, text, flags=re.IGNORECASE | re.DOTALL)
    stripped = text[: match.start()] if match is not None else text
    start_index = stripped.lower().find("<tool_call")
    if start_index != -1:
        stripped = stripped[:start_index]
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def normalize_thinking_phase_text_for_rendering(text: str) -> str:
    stripped = _strip_tool_call_markup(text)
    if not stripped:
        return stripped
    stripped = re.sub(_THINKING_MARKER_LINE_REGEX, "", stripped, flags=re.IGNORECASE | re.MULTILINE)
    stripped = re.sub(_THINKING_MARKER_REGEX, "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def build_thinking_phase(
    *,
    phase_id: str,
    sequence_index: int,
    anchor_type: str,
    anchor_call_id: str | None,
    anchor_position: int | None,
    phase_text: str,
    duration_ms: int | None,
    status: str,
    started_at_ms: int | None = None,
    committed_preface_text: str | None = None,
) -> JSONDict | None:
    normalized_phase_text = normalize_thinking_phase_text_for_rendering(phase_text)
    resolution = None
    if committed_preface_text is not None:
        resolution = resolve_committed_thinking_preface_rendering(
            normalized_phase_text,
            committed_preface_text,
        )
        if resolution is None:
            raise ValidationError("Committed thinking preface no longer matches phase text.")
    elif status == "running":
        resolution = resolve_thinking_preface_rendering(
            normalized_phase_text,
            require_complete_preface=True,
        )
    else:
        resolution = resolve_thinking_preface_rendering(
            normalized_phase_text,
            require_complete_preface=False,
        )
    if resolution is None:
        return None
    phase_payload: JSONDict = {
        "phase_id": phase_id,
        "sequence_index": sequence_index,
        "anchor_type": anchor_type,
        "text": resolution.text,
        "render_mode": resolution.render_mode,
        "preface_complete": resolution.preface_complete,
        "status": status,
        "collapsed": True,
    }
    if anchor_type == "position":
        phase_payload["anchor_position"] = max(
            0,
            anchor_position if anchor_position is not None else 0,
        )
    elif anchor_type in {"before_call", "after_call"} and anchor_call_id is not None:
        phase_payload["anchor_call_id"] = anchor_call_id
    else:
        raise ValidationError("Thinking phase anchor metadata is invalid.")
    if resolution.preface_text is not None:
        phase_payload["preface_text"] = resolution.preface_text
    if duration_ms is not None and duration_ms >= 0:
        phase_payload["duration_ms"] = duration_ms
    if started_at_ms is not None and started_at_ms >= 0:
        phase_payload["started_at_ms"] = started_at_ms
    return phase_payload
