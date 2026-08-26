"""SoAI - Assistant timeline presentation projection [backend/core/assistant_timeline/presentation_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("project_assistant_event_timeline",)

_TEXT_EVENT_TYPE = "assistant_text_delta"


def _project_text_run(events: list[JSONDict]) -> JSONDict:
    first = events[0]
    last = events[-1]
    first_sequence = first.get("sequence")
    last_sequence = last.get("sequence")
    last_revision = last.get("assistant_revision")
    last_payload = last.get("payload")
    if not isinstance(first_sequence, int) or not isinstance(last_sequence, int):
        raise ValidationError("Validated assistant timeline text sequence is invalid.")
    if not isinstance(last_revision, int) or not isinstance(last_payload, dict):
        raise ValidationError("Validated assistant timeline text payload is invalid.")
    deltas: list[str] = []
    latest_usage_preview = None
    usage_preview_observed = False
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise ValidationError("Validated assistant timeline text payload is invalid.")
        delta = payload.get("delta")
        if not isinstance(delta, str) or not delta:
            raise ValidationError("Validated assistant timeline text delta is invalid.")
        deltas.append(delta)
        if "usage_preview" in payload:
            latest_usage_preview = payload["usage_preview"]
            usage_preview_observed = True
    projected_payload = dict(last_payload)
    projected_payload["delta"] = "".join(deltas)
    if usage_preview_observed:
        projected_payload["usage_preview"] = latest_usage_preview
    return {
        "source_sequence_start": first_sequence,
        "sequence": last_sequence,
        "assistant_revision": last_revision,
        "event_type": _TEXT_EVENT_TYPE,
        "payload": projected_payload,
    }


def _project_single_event(event: JSONDict) -> JSONDict:
    sequence = event.get("sequence")
    if not isinstance(sequence, int):
        raise ValidationError("Validated assistant timeline sequence is invalid.")
    return {**event, "source_sequence_start": sequence}


def project_assistant_event_timeline(
    timeline: Sequence[JSONValue],
) -> list[JSONDict]:
    projected: list[JSONDict] = []
    text_run: list[JSONDict] = []
    for event in timeline:
        if not is_json_dict(event):
            raise ValidationError("Validated assistant timeline event is invalid.")
        if event.get("event_type") == _TEXT_EVENT_TYPE:
            text_run.append(event)
            continue
        if text_run:
            projected.append(_project_text_run(text_run))
            text_run = []
        projected.append(_project_single_event(event))
    if text_run:
        projected.append(_project_text_run(text_run))
    return projected
