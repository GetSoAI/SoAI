"""SoAI - Messaging delivery account and claim fencing [backend/app/background/messaging_delivery_fencing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.messaging_delivery_observability import report_delivery_chunk_state
from core.errors.exceptions import StateError
from core.messaging.delivery_models import MESSAGING_DELIVERY_CLAIM_OWNER
from core.types.json import is_json_dict
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.messaging.delivery_models import MessagingDeliveryAttempt
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "load_messaging_transport_account",
    "record_delivery_pre_send_retry",
    "record_delivery_terminal_failure",
)

PRE_SEND_RETRY_DELAY_MS = 1_000


async def record_delivery_pre_send_retry(
    deliveries: DatabaseMessagingDeliveriesProtocol,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
    failure_code: str,
) -> None:
    recorded = await deliveries.record_claim_not_started(
        delivery_id=attempt.delivery_id,
        claim_generation=attempt.claim_generation,
        claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
        server_boot_id=server_boot_id,
        ordinal=attempt.ordinal,
        failure_code=failure_code,
        retry_after_ms=PRE_SEND_RETRY_DELAY_MS,
    )
    current = recorded.get("state") != "stale"
    report_delivery_chunk_state(
        attempt,
        outcome="retryable" if current else "superseded",
        outcome_detail=("pre_send_retry" if current else "pre_send_retry_superseded"),
        failure_code=(failure_code if current else "messaging_delivery_fence_changed"),
        retry_after_ms=PRE_SEND_RETRY_DELAY_MS if current else None,
    )


async def record_delivery_terminal_failure(
    deliveries: DatabaseMessagingDeliveriesProtocol,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
    failure_code: str,
) -> None:
    recorded = await deliveries.record_claim_pre_send_failure(
        delivery_id=attempt.delivery_id,
        claim_generation=attempt.claim_generation,
        claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
        server_boot_id=server_boot_id,
        ordinal=attempt.ordinal,
        failure_code=failure_code,
    )
    current = recorded.get("state") != "stale"
    report_delivery_chunk_state(
        attempt,
        outcome="failure" if current else "superseded",
        outcome_detail=("pre_send_terminal" if current else "pre_send_terminal_superseded"),
        failure_code=(failure_code if current else "messaging_delivery_fence_changed"),
    )


async def load_messaging_transport_account(
    accounts: DatabaseMessagingAccountsProtocol,
    deliveries: DatabaseMessagingDeliveriesProtocol,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
) -> JSONDict | None:
    account = await accounts.get_transport_account(attempt.account_id, attempt.platform)
    if account is None:
        await record_delivery_terminal_failure(
            deliveries,
            attempt,
            server_boot_id,
            "messaging_transport_account_unavailable",
        )
        return None
    if account.get("user_id") != attempt.user_id:
        raise StateError("Messaging delivery account ownership is invalid.")
    credentials = account.get("credentials")
    if not is_json_dict(credentials):
        raise StateError("Messaging delivery credentials are invalid.")
    coerce_required_non_empty_str(
        account.get("credential_fingerprint"),
        label="Messaging credential fingerprint",
    )
    return account
