"""SoAI - Messaging account provider reconciliation [backend/features/messaging/account_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.messaging.account_validation import (
    require_messaging_account_fence,
    require_messaging_account_lifecycle_state,
)
from core.messaging.callback_contracts import (
    MessagingCallbackMutation,
    require_messaging_callback_ownership_state,
)
from features.messaging.account_callback_reconciliation import (
    reconcile_messaging_account_callback,
    remove_messaging_account_callback,
)
from features.messaging.account_transition_reporting import (
    report_messaging_account_transition,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.account_models import MessagingAccountLifecycleState
    from core.messaging.callback_contracts import MessagingCallbackOwnershipState
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from core.types.json import JSONDict

__all__ = ("reconcile_committed_messaging_account",)

LOGGER_NAME = "SoAI.features.messaging.account_reconciliation"
OPERATION_RECONCILE = "messaging.account.reconcile"


def _failed_ownership_state(
    account: JSONDict,
    error_details: JSONDict | None,
) -> MessagingCallbackOwnershipState:
    if error_details is not None and error_details.get("callback_ownership_state") == "external":
        return "external"
    value = account.get("callback_ownership_state")
    return require_messaging_callback_ownership_state(
        value if isinstance(value, str) else None,
    )


async def _resolve_provider_reconciliation(
    *,
    http_client: httpx2.AsyncClient,
    public_origin: str,
    account: JSONDict,
    platform: MessagingPlatform,
    lifecycle_state: MessagingAccountLifecycleState,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> tuple[MessagingCallbackMutation, bool | None, str | None]:
    if lifecycle_state == "disabled":
        mutation = await remove_messaging_account_callback(
            http_client,
            account=account,
            public_origin=public_origin,
        )
        return (mutation, True, None)
    mutation = await reconcile_messaging_account_callback(
        http_client,
        account=account,
        public_origin=public_origin,
        replace_existing_callback=replace_existing_callback,
        refresh_owned_callback=refresh_owned_callback,
    )
    if platform == "discord":
        return (mutation, None, "discord_listener_starting")
    return (mutation, True, None)


async def _reconcile_messaging_account_locked(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    http_client: httpx2.AsyncClient,
    public_origin: str,
    account: JSONDict,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> JSONDict:
    fence = require_messaging_account_fence(account)
    lifecycle_state_value = account.get("lifecycle_state")
    if not isinstance(lifecycle_state_value, str):
        raise StateError("Messaging account lifecycle state is invalid.")
    lifecycle_state = require_messaging_account_lifecycle_state(lifecycle_state_value)
    if lifecycle_state == "deleting":
        raise StateError("Messaging account cannot be reconciled while deleting.")
    try:
        mutation, healthy, health_code = await _resolve_provider_reconciliation(
            http_client=http_client,
            public_origin=public_origin,
            account=account,
            platform=fence.platform,
            lifecycle_state=lifecycle_state,
            replace_existing_callback=replace_existing_callback,
            refresh_owned_callback=refresh_owned_callback,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=OPERATION_RECONCILE)
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Messaging account external reconciliation failed.",
            operation=OPERATION_RECONCILE,
            level="warning",
            details={"account_id": fence.account_id, "platform": fence.platform},
        )
        installed_fingerprint = account.get("installed_callback_fingerprint")
        mutation = MessagingCallbackMutation(
            callback_fingerprint=(
                installed_fingerprint if isinstance(installed_fingerprint, str) else None
            ),
            ownership_state=_failed_ownership_state(
                account,
                dict(error.details) if error.details is not None else None,
            ),
        )
        healthy = False
        health_code = str(error.code)[:120]
    result = await database_accounts.record_reconciliation(
        user_id=fence.user_id,
        account_id=fence.account_id,
        expected_revision=fence.revision,
        lifecycle_generation=fence.lifecycle_generation,
        healthy=healthy,
        callback_fingerprint=mutation.callback_fingerprint,
        ownership_state=mutation.ownership_state,
        health_code=health_code,
    )
    report_messaging_account_transition(
        operation=OPERATION_RECONCILE,
        platform=fence.platform,
        account_id=fence.account_id,
        before=result.before if result is not None else account,
        after=result.after if result is not None else None,
    )
    if result is not None:
        return result.after
    latest = await database_accounts.get_account(fence.user_id, fence.account_id)
    if latest is None:
        raise StateError("Messaging account disappeared during reconciliation.")
    return latest


async def reconcile_committed_messaging_account(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    http_client: httpx2.AsyncClient,
    public_origin: str,
    account: JSONDict,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> JSONDict:
    fence = require_messaging_account_fence(account)
    async with database_accounts.account_lifecycle_lock(fence.account_id):
        latest = await database_accounts.get_transport_account(
            fence.account_id,
            fence.platform,
        )
        if latest is None:
            raise StateError("Messaging account disappeared before reconciliation.")
        latest_fence = require_messaging_account_fence(latest)
        if latest_fence != fence:
            public_latest = await database_accounts.get_account(
                latest_fence.user_id,
                latest_fence.account_id,
            )
            if public_latest is None:
                raise StateError("Messaging account disappeared before reconciliation.")
            return public_latest
        return await _reconcile_messaging_account_locked(
            database_accounts=database_accounts,
            http_client=http_client,
            public_origin=public_origin,
            account=latest,
            replace_existing_callback=replace_existing_callback,
            refresh_owned_callback=refresh_owned_callback,
        )
