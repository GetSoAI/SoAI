"""SoAI - WebUI mail account routes [backend/features/api/routes/webui/mail/routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from core.errors.exceptions import ValidationError
from features.api.routes.webui.external_accounts.account_route_registration import (
    DomainAccountRouteSpec,
    register_domain_account_routes,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "register_mail_routes",
    "register_routes",
)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)


def register_mail_routes(routers: ApiRouters) -> None:
    register_routes(routers)


def register_endpoints(router: APIRouter) -> None:
    register_domain_account_routes(
        router,
        base_path="/users/me/mail/accounts",
        spec=DomainAccountRouteSpec(
            account_type="mail",
            invalid_payload_message="Request body must be a JSON object.",
            server_error_message="Mail payload is invalid.",
            create_audit_event="MAIL_ACCOUNT_CREATED",
            update_audit_event="MAIL_ACCOUNT_UPDATED",
            delete_audit_event="MAIL_ACCOUNT_DELETED",
            test_audit_event="MAIL_ACCOUNT_TESTED",
            sync_audit_event="MAIL_ACCOUNT_SYNCED",
            oauth_start_audit_event="MAIL_ACCOUNT_OAUTH_STARTED",
            oauth_clear_audit_event="MAIL_ACCOUNT_OAUTH_CLEARED",
            create_subject="mail_account",
            not_found_message="Mail account not found.",
            resolve_accounts=lambda api_context: api_context.dependencies.mail_accounts,
            sync_account=_sync_mail_account,
        ),
    )


async def _sync_mail_account(
    api_context: ApiContext,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> JSONDict:
    folder_id_value = payload.get("folder_id")
    if folder_id_value is not None and not isinstance(folder_id_value, str):
        raise ValidationError("folder_id is invalid.")
    folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else None
    return await api_context.dependencies.mail.sync_account(
        user_id=user_id,
        account_id=account_id,
        folder_id=folder_id or None,
    )
