"""SoAI - Shared model discovery command publication [backend/core/models/discovery_trigger.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.completion_waiting import (
    EventPublicationReceipt,
    await_publication_receipt,
)
from core.events.protocols import EventBusProtocol
from core.events.types_models_model_commands import TriggerModelDiscoveryCommand

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext

__all__ = ("publish_model_discovery_request",)


async def publish_model_discovery_request(
    event_bus: EventBusProtocol,
    *,
    plugins_to_scan: list[str] | None = None,
    context: RequestContext | None = None,
    wait_for_completion: bool = False,
) -> None:
    command = TriggerModelDiscoveryCommand(
        plugins_to_scan=list(plugins_to_scan) if plugins_to_scan else None,
        context=context,
        wait_for_completion=wait_for_completion,
    )
    if not wait_for_completion:
        await event_bus.publish(command)
        return
    receipt = EventPublicationReceipt.create(
        event_type=TriggerModelDiscoveryCommand.__name__,
        operation="models.discovery_trigger.publish_and_wait",
    )
    await event_bus.publish(command, wait_for_completion=receipt.completion_signal)
    await await_publication_receipt(receipt)
