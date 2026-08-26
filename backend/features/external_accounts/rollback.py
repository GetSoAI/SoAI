"""SoAI - External account rollback helpers [backend/features/external_accounts/rollback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "restore_external_account",
    "rollback_external_account_creation",
)

OPERATION = "features.external_accounts.rollback"


async def rollback_external_account_creation(
    *,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    external_account_id: str,
    logger: LoggerProtocol,
    owner: str,
) -> None:
    try:
        await run_idempotent_current_task_operation(
            partial(
                external_accounts.delete_account,
                user_id=user_id,
                external_account_id=external_account_id,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise _log_and_coerce_rollback_failure(
            exception,
            logger=logger,
            message="Failed to roll back external account after dependent account creation failure.",
            owner=owner,
            user_id=user_id,
            external_account_id=external_account_id,
        ) from exception


async def restore_external_account(
    *,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    external_account_id: str,
    previous_account: JSONDict,
    logger: LoggerProtocol,
    owner: str,
) -> None:
    try:
        restored = await run_idempotent_current_task_operation(
            partial(
                external_accounts.update_account,
                user_id=user_id,
                external_account_id=external_account_id,
                updates=_build_restore_updates(previous_account),
            ),
        )
        if restored is None:
            raise StateError("External account restore target was not found.")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise _log_and_coerce_rollback_failure(
            exception,
            logger=logger,
            message="Failed to restore external account after dependent account update failure.",
            owner=owner,
            user_id=user_id,
            external_account_id=external_account_id,
        ) from exception


def _log_and_coerce_rollback_failure(
    exception: Exception,
    *,
    logger: LoggerProtocol,
    message: str,
    owner: str,
    user_id: int,
    external_account_id: str,
) -> SoAIError:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION,
    )
    log_exception(
        logger,
        coerced,
        message=message,
        operation=OPERATION,
        details={
            "owner": owner,
            "user_id": user_id,
            "external_account_id": external_account_id,
        },
    )
    return coerced


def _build_restore_updates(account: JSONDict) -> JSONDict:
    return {
        "label": account.get("label"),
        "username": account.get("username"),
        "auth_type": account.get("auth_type"),
        "password": account.get("password"),
        "oauth_status": account.get("oauth_status"),
        "oauth_client_id": account.get("oauth_client_id"),
        "oauth_client_secret": account.get("oauth_client_secret"),
        "oauth_access_token": account.get("oauth_access_token"),
        "oauth_refresh_token": account.get("oauth_refresh_token"),
        "oauth_expires_at_ms": account.get("oauth_expires_at_ms"),
        "oauth_resource_metadata_url": account.get("oauth_resource_metadata_url"),
        "oauth_auth_server_issuer": account.get("oauth_auth_server_issuer"),
        "oauth_authorization_endpoint": account.get("oauth_authorization_endpoint"),
        "oauth_token_endpoint": account.get("oauth_token_endpoint"),
        "oauth_registration_endpoint": account.get("oauth_registration_endpoint"),
        "oauth_token_endpoint_auth_method": account.get("oauth_token_endpoint_auth_method"),
        "oauth_scopes": account.get("oauth_scopes"),
        "oauth_required_scopes": account.get("oauth_required_scopes"),
    }
