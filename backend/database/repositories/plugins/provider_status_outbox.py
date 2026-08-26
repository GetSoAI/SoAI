"""SoAI - Runtime provider status domain-event outbox writes [backend/database/repositories/plugins/provider_status_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.events.domain_event_payload import build_domain_event_payload
from core.events.id_generation import generate_event_id
from database.repositories.event_outbox.sync_ops import (
    sync_enqueue_domain_event_payload,
)

__all__ = ("enqueue_provider_status_event",)


def enqueue_provider_status_event(
    connection: sqlite3.Connection,
    plugin_name: str,
    provider_id: str,
    new_status: str,
    error: str | None,
    created_at_ms: int,
) -> None:
    payload = build_domain_event_payload(
        fields={
            "plugin_name": plugin_name,
            "provider_id": provider_id,
            "new_status": new_status,
            "error": error,
        },
        event_id=generate_event_id(),
        timestamp_unix=created_at_ms / 1000,
    )
    sync_enqueue_domain_event_payload(
        connection,
        event_type="ProviderStatusUpdatedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )
