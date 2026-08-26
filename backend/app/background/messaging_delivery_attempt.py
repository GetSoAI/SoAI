"""SoAI - Fenced outbound Messaging chunk attempts [backend/app/background/messaging_delivery_attempt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from app.background.messaging_delivery_fencing import (
    load_messaging_transport_account,
    record_delivery_pre_send_retry,
    record_delivery_terminal_failure,
)
from app.background.messaging_delivery_observability import report_delivery_chunk_state
from core.concurrency.cancellation_cleanup import uncancel_and_wait, uncancel_then_cleanup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.messaging.delivery_models import MESSAGING_DELIVERY_CLAIM_OWNER
from core.types.json import is_json_dict
from core.validation.strings import coerce_required_non_empty_str
from features.messaging.provider_delivery import execute_messaging_provider_text_request
from features.messaging.provider_delivery_requests import build_messaging_text_request

if TYPE_CHECKING:
    from core.messaging.delivery_models import MessagingDeliveryAttempt
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
    )
    from features.messaging.provider_delivery_requests import MessagingProviderRequest

__all__ = ("execute_messaging_delivery_attempt",)

LOGGER_NAME = "SoAI.app.background.messaging_delivery_attempt"
OPERATION_PRE_SEND = "messaging.delivery.pre_send"


async def _record_provider_outcome(
    *,
    deliveries: DatabaseMessagingDeliveriesProtocol,
    http_client: httpx2.AsyncClient,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
    request: MessagingProviderRequest,
    credential_fingerprint: str,
) -> None:
    try:
        started = await deliveries.mark_chunk_request_started(
            delivery_id=attempt.delivery_id,
            claim_generation=attempt.claim_generation,
            claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
            server_boot_id=server_boot_id,
            ordinal=attempt.ordinal,
            credential_fingerprint=credential_fingerprint,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Messaging provider request authorization failed before execution.",
            operation=OPERATION_PRE_SEND,
            level="warning",
            details={"delivery_id": attempt.delivery_id, "ordinal": attempt.ordinal},
        )
        await record_delivery_pre_send_retry(
            deliveries,
            attempt,
            server_boot_id,
            "delivery_request_authorization_failed",
        )
        return
    if not started:
        await record_delivery_pre_send_retry(
            deliveries,
            attempt,
            server_boot_id,
            "messaging_delivery_fence_changed",
        )
        return
    report_delivery_chunk_state(
        attempt,
        outcome="success",
        outcome_detail="provider_request_started",
    )
    outcome = await execute_messaging_provider_text_request(
        http_client=http_client,
        platform=attempt.platform,
        request=request,
        delivery_id=attempt.delivery_id,
        ordinal=attempt.ordinal,
    )
    if outcome.state == "sent":
        if outcome.provider_message_id is None:
            raise StateError("Provider delivery success is missing a message id.")
        recorded = await deliveries.record_chunk_sent(
            delivery_id=attempt.delivery_id,
            claim_generation=attempt.claim_generation,
            claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
            server_boot_id=server_boot_id,
            ordinal=attempt.ordinal,
            provider_message_id=outcome.provider_message_id,
            next_request_delay_ms=outcome.next_request_delay_ms or 0,
        )
        current = recorded.get("state") != "stale"
        report_delivery_chunk_state(
            attempt,
            outcome="success" if current else "superseded",
            outcome_detail="sent" if current else "send_fence_changed",
            failure_code=None if current else "messaging_delivery_fence_changed",
        )
        return
    if outcome.failure_code is None:
        raise StateError("Provider delivery failure is missing a code.")
    recorded = await deliveries.record_chunk_failure(
        delivery_id=attempt.delivery_id,
        claim_generation=attempt.claim_generation,
        claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
        server_boot_id=server_boot_id,
        ordinal=attempt.ordinal,
        outcome=outcome.state,
        failure_code=outcome.failure_code,
        retry_after_ms=outcome.retry_after_ms,
    )
    current = recorded.get("state") != "stale"
    report_delivery_chunk_state(
        attempt,
        outcome=outcome.state if current else "superseded",
        outcome_detail=("provider_outcome_recorded" if current else "provider_outcome_superseded"),
        failure_code=(outcome.failure_code if current else "messaging_delivery_fence_changed"),
        retry_after_ms=outcome.retry_after_ms if current else None,
    )


async def execute_messaging_delivery_attempt(
    *,
    deliveries: DatabaseMessagingDeliveriesProtocol,
    accounts: DatabaseMessagingAccountsProtocol,
    http_client: httpx2.AsyncClient,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
) -> None:
    try:
        account = await load_messaging_transport_account(
            accounts,
            deliveries,
            attempt,
            server_boot_id,
        )
        if account is None:
            return
        credentials = account.get("credentials")
        if not is_json_dict(credentials):
            raise StateError("Messaging delivery credentials disappeared before send.")
        credential_fingerprint = coerce_required_non_empty_str(
            account.get("credential_fingerprint"),
            label="Messaging credential fingerprint",
        )
        request = build_messaging_text_request(
            platform=attempt.platform,
            credentials=credentials,
            remote_thread_key=attempt.remote_thread_key,
            content_text=attempt.content_text,
            delivery_id=attempt.delivery_id,
            ordinal=attempt.ordinal,
        )
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            record_delivery_pre_send_retry(
                deliveries,
                attempt,
                server_boot_id,
                "delivery_cancelled_before_request_start",
            ),
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Messaging delivery pre-send preparation failed operationally.",
            operation=OPERATION_PRE_SEND,
            level="warning",
            details={"delivery_id": attempt.delivery_id, "ordinal": attempt.ordinal},
        )
        await record_delivery_pre_send_retry(
            deliveries,
            attempt,
            server_boot_id,
            "delivery_pre_send_operational_failure",
        )
        return
    except (StateError, ValidationError):
        await record_delivery_terminal_failure(
            deliveries,
            attempt,
            server_boot_id,
            "messaging_delivery_state_invalid",
        )
        return
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Messaging delivery failed unexpectedly before provider request start.",
            operation=OPERATION_PRE_SEND,
            details={
                "delivery_id": attempt.delivery_id,
                "ordinal": attempt.ordinal,
            },
        )
        await record_delivery_terminal_failure(
            deliveries,
            attempt,
            server_boot_id,
            "messaging_delivery_unexpected_pre_send_failure",
        )
        return
    provider_execution_started = False
    try:
        async with accounts.account_lifecycle_lock(attempt.account_id):
            provider_execution_started = True
            await uncancel_and_wait(
                _record_provider_outcome(
                    deliveries=deliveries,
                    http_client=http_client,
                    attempt=attempt,
                    server_boot_id=server_boot_id,
                    request=request,
                    credential_fingerprint=credential_fingerprint,
                ),
            )
    except asyncio.CancelledError:
        if not provider_execution_started:
            await uncancel_then_cleanup(
                record_delivery_pre_send_retry(
                    deliveries,
                    attempt,
                    server_boot_id,
                    "delivery_cancelled_before_request_start",
                ),
            )
        raise
