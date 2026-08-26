"""SoAI - Messaging Gateway dependency contract [backend/app/background/messaging_gateway_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
        DatabaseMessagingIngressProtocol,
    )
    from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol
    from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol

__all__ = ("MessagingGatewayDependencies",)


@dataclass(frozen=True, slots=True)
class MessagingGatewayDependencies:
    runtime_state: RuntimeStateStoreProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_messaging_accounts: DatabaseMessagingAccountsProtocol
    database_messaging_ingress: DatabaseMessagingIngressProtocol
    database_messaging_deliveries: DatabaseMessagingDeliveriesProtocol
    durable_delivery: DurableEventDeliveryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    event_bus: EventBusProtocol
    licensing_status: LicensingStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingGatewayDependencies",
            runtime_state=self.runtime_state,
            runtime_flags=self.runtime_flags,
            http_client=self.http_client,
            database_messaging_accounts=self.database_messaging_accounts,
            database_messaging_ingress=self.database_messaging_ingress,
            database_messaging_deliveries=self.database_messaging_deliveries,
            durable_delivery=self.durable_delivery,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            event_bus=self.event_bus,
            licensing_status=self.licensing_status,
        )
