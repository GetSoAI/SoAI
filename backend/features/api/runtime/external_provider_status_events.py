"""SoAI - External provider status event publication [backend/features/api/runtime/external_provider_status_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.protocols import EventBusProtocol
from core.events.types_plugins import ProviderStatusUpdatedEvent
from core.models.external_provider_record import ExternalProviderRecord

__all__ = ("publish_external_provider_status_event",)


async def publish_external_provider_status_event(
    event_bus: EventBusProtocol,
    *,
    plugin_name: str,
    provider_id: str,
    provider_record: ExternalProviderRecord,
    default_status: str,
) -> None:
    provider_status = provider_record.get("last_status")
    event_status = provider_status if isinstance(provider_status, str) else default_status
    provider_error = provider_record.get("last_error")
    event_error = provider_error if isinstance(provider_error, str) else None
    await event_bus.publish(
        ProviderStatusUpdatedEvent(
            plugin_name,
            provider_id,
            event_status,
            event_error,
        ),
    )
