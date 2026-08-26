"""SoAI - Communications sync actor account iterations [backend/app/background/communications_sync_actor_iterations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.communications_sync_actor_support import (
    SyncBackoffState,
    clear_sync_backoff,
    extract_account_id,
    extract_accounts,
    extract_user_ids,
    is_sync_due,
    notify_resource_updated,
    prune_sync_backoff,
    register_sync_backoff_failure,
    supports_action,
)
from core.config.clamped_numeric import read_config_int_min_clamped
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    RateLimitError,
    ServiceUnavailableError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.external_service_exception import ExternalServiceError
from core.errors.messages import resolve_exception_error_message
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.types.json import JSONValue
from mcp.calendar.resource_uris import CALENDAR_RESOURCE_URI
from mcp.mail.resource_uris import MAIL_RESOURCE_URI

if TYPE_CHECKING:
    from core.calendar.protocols import CalendarServiceProtocol
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import LinkedAccountQueryProtocol
    from core.logging.protocols import LoggerProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "run_calendar_sync_iteration",
    "run_mail_sync_iteration",
)

OPERATION = "app.background.communications_sync_actor.run"

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict

    type AccountListCall = Callable[[int], Awaitable[JSONDict]]
    type AccountSyncCall = Callable[[int, str], Awaitable[JSONDict]]


async def _run_domain_sync_iteration(
    *,
    config: ConfigProtocol,
    database_users: DatabaseUsersProtocol,
    domain: str,
    enabled_key: str,
    interval_key: str,
    list_accounts: AccountListCall,
    sync_account: AccountSyncCall,
    resource_uri: str,
    logger: LoggerProtocol,
    mcp_server: MCPServerProtocol | None,
    backoff_state: dict[str, SyncBackoffState],
) -> None:
    if not bool(config.get_bool(enabled_key)):
        return
    resource_changed = False
    interval_seconds = read_config_int_min_clamped(
        config,
        interval_key,
        0,
        minimum=1,
    )
    interval_ms = interval_seconds * 1000
    active_account_ids: set[str] = set()
    listed_all_users = True
    try:
        user_ids = extract_user_ids(await database_users.list_human_users())
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"{domain.capitalize()} background sync user listing failed.",
            operation=OPERATION,
            level="warning",
            details={"domain": domain},
        )
        return
    for user_id in user_ids:
        try:
            accounts = extract_accounts(await list_accounts(user_id))
        except RECOVERABLE_EXCEPTIONS as exception:
            listed_all_users = False
            log_exception(
                logger,
                exception,
                message=f"{domain.capitalize()} background sync skipped user account listing.",
                operation=OPERATION,
                level="warning",
                details={"domain": domain, "user_id": user_id},
            )
            continue
        for account in accounts:
            account_id = extract_account_id(account)
            active_account_ids.add(account_id)
            try:
                can_sync = supports_action(account, action="sync")
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"{domain.capitalize()} background sync skipped invalid account entry.",
                    operation=OPERATION,
                    level="warning",
                    details={
                        "domain": domain,
                        "user_id": user_id,
                        "account_id": account_id,
                    },
                )
                clear_sync_backoff(backoff_state, account_id=account_id)
                continue
            if not can_sync:
                clear_sync_backoff(backoff_state, account_id=account_id)
                continue
            if not is_sync_due(backoff_state, account_id=account_id):
                continue
            try:
                await sync_account(user_id, account_id)
            except RECOVERABLE_EXCEPTIONS as exception:
                delay_ms = register_sync_backoff_failure(
                    backoff_state,
                    account_id=account_id,
                    interval_ms=interval_ms,
                )
                reason = resolve_exception_error_message(exception)
                details: dict[str, JSONValue] = {
                    "domain": domain,
                    "account_id": account_id,
                    "user_id": int(user_id),
                    "retry_delay_ms": int(delay_ms),
                }
                if _is_expected_background_sync_exception(exception):
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"{domain.capitalize()} background sync failed: {reason}",
                        operation=OPERATION,
                        level="warning",
                        details=details,
                    )
                else:
                    log_exception(
                        logger,
                        exception,
                        message=f"{domain.capitalize()} background sync failed.",
                        operation=OPERATION,
                        level="warning",
                        details=details,
                    )
            else:
                clear_sync_backoff(backoff_state, account_id=account_id)
                resource_changed = True
    if listed_all_users:
        prune_sync_backoff(backoff_state, active_account_ids=active_account_ids)
    if resource_changed:
        await notify_resource_updated(logger=logger, server=mcp_server, uri=resource_uri)


async def run_mail_sync_iteration(
    *,
    config: ConfigProtocol,
    database_users: DatabaseUsersProtocol,
    mail: MailServiceProtocol,
    account_queries: LinkedAccountQueryProtocol,
    logger: LoggerProtocol,
    mcp_server: MCPServerProtocol | None,
    backoff_state: dict[str, SyncBackoffState],
) -> None:
    await _run_domain_sync_iteration(
        config=config,
        database_users=database_users,
        domain="mail",
        enabled_key="INTEGRATIONS.MAIL.SYNC.ENABLED",
        interval_key="INTEGRATIONS.MAIL.SYNC.INTERVAL_SEC",
        list_accounts=account_queries.list_accounts,
        sync_account=lambda user_id, account_id: mail.sync_account(
            user_id=user_id,
            account_id=account_id,
            folder_id=None,
        ),
        resource_uri=MAIL_RESOURCE_URI,
        logger=logger,
        mcp_server=mcp_server,
        backoff_state=backoff_state,
    )


async def run_calendar_sync_iteration(
    *,
    config: ConfigProtocol,
    database_users: DatabaseUsersProtocol,
    calendar: CalendarServiceProtocol,
    account_queries: LinkedAccountQueryProtocol,
    logger: LoggerProtocol,
    mcp_server: MCPServerProtocol | None,
    backoff_state: dict[str, SyncBackoffState],
) -> None:
    await _run_domain_sync_iteration(
        config=config,
        database_users=database_users,
        domain="calendar",
        enabled_key="INTEGRATIONS.CALENDAR.SYNC.ENABLED",
        interval_key="INTEGRATIONS.CALENDAR.SYNC.INTERVAL_SEC",
        list_accounts=account_queries.list_accounts,
        sync_account=lambda user_id, account_id: calendar.sync_account(
            user_id=user_id,
            account_id=account_id,
        ),
        resource_uri=CALENDAR_RESOURCE_URI,
        logger=logger,
        mcp_server=mcp_server,
        backoff_state=backoff_state,
    )


def _is_expected_background_sync_exception(exception: BaseException) -> bool:
    if isinstance(
        exception,
        ExternalServiceError
        | RateLimitError
        | ServiceUnavailableError
        | SoAITimeoutError
        | ValidationError,
    ):
        return True
    if isinstance(exception, OSError | TimeoutError):
        return True
    return False
