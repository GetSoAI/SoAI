"""SoAI - Messaging webhook account recovery lifecycle [backend/app/background/messaging_gateway_webhook_account.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.messaging.account_validation import require_messaging_account_fence
from core.messaging.observability_fields import MessagingLogFields
from core.timing.retry_backoff import compute_uniform_delay_seconds
from features.messaging.account_reconciliation import (
    reconcile_committed_messaging_account,
)
from features.messaging.account_recovery_backoff import (
    wait_for_messaging_account_recovery,
)

if TYPE_CHECKING:
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from core.types.json import JSONDict

__all__ = (
    "MessagingWebhookAccountDependencies",
    "run_messaging_webhook_account",
)

WEBHOOK_MONITOR_MINIMUM_SECONDS = 270.0
WEBHOOK_MONITOR_MAXIMUM_SECONDS = 330.0


@dataclass(frozen=True, slots=True)
class MessagingWebhookAccountDependencies:
    database_accounts: DatabaseMessagingAccountsProtocol
    http_client: httpx2.AsyncClient
    public_origin: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingWebhookAccountDependencies",
            database_accounts=self.database_accounts,
            http_client=self.http_client,
            public_origin=self.public_origin,
        )


async def run_messaging_webhook_account(
    *,
    deps: MessagingWebhookAccountDependencies,
    account: JSONDict,
    shutdown_event: asyncio.Event,
) -> None:
    reconnect_attempt = 0
    fence = require_messaging_account_fence(account)
    if fence.platform not in ("telegram", "whatsapp"):
        raise StateError("Messaging webhook reconciliation platform is invalid.")
    log_fields = MessagingLogFields(
        operation="messaging.webhook.account_runtime",
        platform=fence.platform,
        account_id=fence.account_id,
        revision=fence.revision,
        lifecycle_generation=fence.lifecycle_generation,
    )
    current = account
    while not shutdown_event.is_set():
        updated = await reconcile_committed_messaging_account(
            database_accounts=deps.database_accounts,
            http_client=deps.http_client,
            public_origin=deps.public_origin,
            account=current,
            replace_existing_callback=False,
            refresh_owned_callback=False,
        )
        lifecycle_state = updated.get("lifecycle_state")
        if lifecycle_state not in ("enabled", "degraded"):
            return
        provider_is_healthy = lifecycle_state == "enabled" and updated.get("health_code") is None
        if provider_is_healthy or updated.get("callback_ownership_state") == "external":
            reconnect_attempt = 0
            monitor_delay = compute_uniform_delay_seconds(
                minimum_seconds=WEBHOOK_MONITOR_MINIMUM_SECONDS,
                maximum_seconds=WEBHOOK_MONITOR_MAXIMUM_SECONDS,
            )
            outcome = await wait_for_shutdown_or_schedule_change(
                shutdown_event,
                None,
                monitor_delay,
            )
            if outcome != "timeout":
                return
        else:
            if not await wait_for_messaging_account_recovery(
                shutdown_event,
                reconnect_attempt,
                log_fields=log_fields,
            ):
                return
            reconnect_attempt += 1
        latest = await deps.database_accounts.get_transport_account(
            fence.account_id,
            fence.platform,
        )
        if latest is None:
            return
        latest_fence = require_messaging_account_fence(latest)
        if latest_fence != fence or latest.get("lifecycle_state") not in ("enabled", "degraded"):
            return
        current = latest
