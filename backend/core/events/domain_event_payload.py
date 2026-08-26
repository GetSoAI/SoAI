"""SoAI - Canonical domain event payload construction [backend/core/events/domain_event_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.errors.exceptions import StateError
from core.events.id_generation import generate_event_id
from core.timing.epoch import epoch_seconds_float
from core.types.json import JSONDict, JSONValue

__all__ = ("build_domain_event_payload",)


def build_domain_event_payload(
    *,
    fields: JSONDict,
    event_id: str | None = None,
    timestamp_unix: float | None = None,
) -> JSONDict:
    if not isinstance(fields, dict):
        raise StateError("Domain event payload fields must be a JSON object.")
    if "event_id" in fields or "timestamp" in fields:
        raise StateError("Domain event payload fields must not override event_id or timestamp.")
    if event_id is None:
        resolved_event_id = generate_event_id()
    else:
        if not isinstance(event_id, str):
            raise StateError("Domain event payload event_id must be a string.")
        resolved_event_id = event_id.strip()
        if not resolved_event_id:
            raise StateError("Domain event payload event_id must be a non-empty string.")
    resolved_timestamp = epoch_seconds_float() if timestamp_unix is None else timestamp_unix
    if (
        isinstance(resolved_timestamp, bool)
        or not isinstance(resolved_timestamp, int | float)
        or not math.isfinite(float(resolved_timestamp))
        or float(resolved_timestamp) <= 0.0
    ):
        raise StateError("Domain event payload timestamp must be a positive finite number.")
    payload: dict[str, JSONValue] = {
        "event_id": resolved_event_id,
        "timestamp": float(resolved_timestamp),
    }
    payload.update(fields)
    return payload
