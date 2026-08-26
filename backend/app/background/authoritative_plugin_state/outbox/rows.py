"""SoAI - Authoritative plugin state outbox claimed row parsing [backend/app/background/authoritative_plugin_state/outbox/rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_trimmed_non_empty_str,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "ClaimedAuthoritativePluginStateOutboxRow",
    "parse_claimed_authoritative_plugin_state_outbox_row",
)


@dataclass(frozen=True, slots=True)
class ClaimedAuthoritativePluginStateOutboxRow:
    outbox_id: int
    attempts: int
    event_id: str
    event_type: str
    payload_json: str


def parse_claimed_authoritative_plugin_state_outbox_row(
    row: SQLiteRowDict,
) -> ClaimedAuthoritativePluginStateOutboxRow:
    label = "Authoritative plugin state outbox row"
    outbox_id = require_sqlite_row_int(row, "id", label=label, minimum=None)
    attempts = require_sqlite_row_int(row, "attempts", label=label, minimum=None)
    event_id = require_sqlite_row_trimmed_non_empty_str(row, "event_id", label=label)
    event_type = require_sqlite_row_trimmed_non_empty_str(row, "event_type", label=label)
    payload_json = require_sqlite_row_trimmed_non_empty_str(row, "payload_json", label=label)
    return ClaimedAuthoritativePluginStateOutboxRow(
        outbox_id=outbox_id,
        attempts=attempts,
        event_id=event_id,
        event_type=event_type,
        payload_json=payload_json,
    )
