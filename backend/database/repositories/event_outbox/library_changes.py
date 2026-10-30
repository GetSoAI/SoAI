"""SoAI - Transactional chat library invalidations [backend/database/repositories/event_outbox/library_changes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import Literal

from core.events.domain_event_payload import build_domain_event_payload
from core.timing.epoch import epoch_ms
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

__all__ = ("sync_enqueue_library_changed",)


def sync_enqueue_library_changed(
    conn: sqlite3.Connection,
    user_id: int,
    event_type: Literal["MemoryLibraryChangedEvent", "ChatPresetLibraryChangedEvent"],
) -> None:
    created_at_ms = epoch_ms()
    sync_enqueue_domain_event_payload(
        conn,
        event_type=event_type,
        payload=build_domain_event_payload(
            fields={"user_id": user_id}, timestamp_unix=created_at_ms / 1000.0
        ),
        created_at_ms=created_at_ms,
    )
