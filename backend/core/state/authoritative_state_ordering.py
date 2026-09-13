"""SoAI - Durable authoritative state publication ordering [backend/core/state/authoritative_state_ordering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.events.types_plugins import AuthoritativeStateChangeEvent
from core.types.json import JSONValue
from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = ("is_stale_authoritative_state_event",)


def is_stale_authoritative_state_event(
    event: AuthoritativeStateChangeEvent,
    current_state: Mapping[str, JSONValue] | None,
) -> bool:
    sequence = require_non_negative_int_strict(
        event.publication_sequence,
        error_message="The state publication position is invalid.",
    )
    current_sequence = require_non_negative_int_strict(
        (current_state.get("publication_sequence", 0) if current_state is not None else 0),
        error_message="The current state publication position is invalid.",
    )
    return sequence < current_sequence
