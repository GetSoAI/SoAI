"""SoAI - Messaging gateway protocol [backend/core/messaging/gateway/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.messaging.ingress_models import NormalizedMessagingEvent
from core.types.json import JSONDict

__all__ = ("MessagingGatewayProtocol",)


class MessagingGatewayProtocol(Protocol):
    def request_reconcile(self) -> None: ...

    async def start(self) -> None: ...

    async def wait_for_initial_reconciliation(self, timeout: float) -> bool: ...

    async def shutdown(self) -> None: ...

    async def admit_event(
        self,
        *,
        account_id: str,
        event: NormalizedMessagingEvent,
    ) -> JSONDict: ...

    async def get_webhook_account(
        self,
        *,
        account_id: str,
        platform: str,
    ) -> JSONDict | None: ...
