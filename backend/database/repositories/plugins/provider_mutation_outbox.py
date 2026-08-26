"""SoAI - Provider mutation domain-event outbox writes [backend/database/repositories/plugins/provider_mutation_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.events.domain_event_payload import build_domain_event_payload
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

__all__ = ("enqueue_provider_invalidations", "enqueue_provider_status_invalidation")


def enqueue_provider_status_invalidation(
    connection: sqlite3.Connection,
    operation_id: str,
    plugin_name: str,
    provider_id: str,
    new_status: str,
    created_at_ms: int,
) -> None:
    payload = build_domain_event_payload(
        fields={
            "plugin_name": plugin_name,
            "provider_id": provider_id,
            "new_status": new_status,
            "error": None,
        },
        event_id=f"{operation_id}:provider-status",
        timestamp_unix=created_at_ms / 1000,
    )
    sync_enqueue_domain_event_payload(
        connection,
        event_type="ProviderStatusUpdatedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )


def enqueue_provider_invalidations(
    connection: sqlite3.Connection,
    operation_id: str,
    plugin_name: str,
    provider_id: str,
    new_status: str,
    provider_revision: int,
    created_at_ms: int,
) -> None:
    enqueue_provider_status_invalidation(
        connection,
        operation_id,
        plugin_name,
        provider_id,
        new_status,
        created_at_ms,
    )
    discovery_payload = build_domain_event_payload(
        fields={
            "plugin_name": plugin_name,
            "provider_id": provider_id,
            "provider_revision": provider_revision,
        },
        event_id=f"{operation_id}:provider-discovery",
        timestamp_unix=created_at_ms / 1000,
    )
    sync_enqueue_domain_event_payload(
        connection,
        event_type="ProviderDiscoveryRequestedEvent",
        payload=discovery_payload,
        created_at_ms=created_at_ms,
    )
