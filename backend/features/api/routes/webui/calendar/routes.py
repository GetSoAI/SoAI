"""SoAI - WebUI calendar account routes [backend/features/api/routes/webui/calendar/routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter

from features.api.routes.webui.external_accounts.account_route_registration import (
    DomainAccountRouteSpec,
    register_domain_account_routes,
)
from features.api.runtime.container.api_routers import ApiRouters

__all__ = (
    "register_calendar_routes",
    "register_routes",
)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)


def register_calendar_routes(routers: ApiRouters) -> None:
    register_routes(routers)


def register_endpoints(router: APIRouter) -> None:
    register_domain_account_routes(
        router,
        base_path="/users/me/calendar/accounts",
        spec=DomainAccountRouteSpec(
            account_type="calendar",
            invalid_payload_message="Request body must be a JSON object.",
            server_error_message="Calendar payload is invalid.",
            create_audit_event="CALENDAR_ACCOUNT_CREATED",
            update_audit_event="CALENDAR_ACCOUNT_UPDATED",
            delete_audit_event="CALENDAR_ACCOUNT_DELETED",
            test_audit_event="CALENDAR_ACCOUNT_TESTED",
            sync_audit_event="CALENDAR_ACCOUNT_SYNCED",
            oauth_start_audit_event="CALENDAR_ACCOUNT_OAUTH_STARTED",
            oauth_clear_audit_event="CALENDAR_ACCOUNT_OAUTH_CLEARED",
            create_subject="calendar_account",
            not_found_message="Calendar account not found.",
            resolve_accounts=lambda api_context: api_context.dependencies.calendar_accounts,
            sync_account=lambda api_context, user_id, account_id, _payload: api_context.dependencies.calendar.sync_account(
                user_id=user_id,
                account_id=account_id,
            ),
        ),
    )
