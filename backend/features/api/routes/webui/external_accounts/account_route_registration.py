"""SoAI - Shared WebUI external-account route registration [backend/features/api/routes/webui/external_accounts/account_route_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.oauth.types import OAuthError
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found
from features.api.runtime.request_payloads import (
    read_optional_json_dict_payload_or_raise,
    read_required_json_dict_payload_or_raise,
)
from features.external_accounts.domain_account_actions import (
    format_account_delete_result,
)

if TYPE_CHECKING:
    from core.external_accounts.linked_account_types import LinkedAccountCapabilities
    from core.types.json import JSONDict

__all__ = (
    "DomainAccountRouteSpec",
    "register_domain_account_routes",
)


@dataclass(frozen=True, slots=True)
class DomainAccountRouteSpec:
    account_type: str
    invalid_payload_message: str
    server_error_message: str
    create_audit_event: str
    update_audit_event: str
    delete_audit_event: str
    test_audit_event: str
    sync_audit_event: str
    oauth_start_audit_event: str
    oauth_clear_audit_event: str
    create_subject: str
    not_found_message: str
    resolve_accounts: Callable[[ApiContext], LinkedAccountCapabilities]
    sync_account: Callable[[ApiContext, int, str, JSONDict], Awaitable[JSONDict]]


async def _execute_domain_account_operation[ResultT](
    request: Request,
    operation: Callable[[], Awaitable[ResultT]],
) -> ResultT:
    try:
        return await operation()
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))


def register_domain_account_routes(
    router: APIRouter,
    *,
    spec: DomainAccountRouteSpec,
    base_path: str,
) -> None:
    @router.get(base_path)
    async def list_accounts(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).queries.list_accounts(
                current_user["id"],
            ),
        )
        return JSONResponse(content=payload)

    @router.post(base_path)
    async def create_account(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload = await read_required_json_dict_payload_or_raise(
            request,
            invalid_message=spec.invalid_payload_message,
            server_error_message=spec.server_error_message,
        )
        log_audit_event(request, spec.create_audit_event, spec.create_subject)
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).creation.create_account(
                user_id=current_user["id"],
                payload=payload,
            ),
        )
        return JSONResponse(content=result)

    @router.patch(f"{base_path}/{{account_id}}")
    async def update_account(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload = await read_required_json_dict_payload_or_raise(
            request,
            invalid_message=spec.invalid_payload_message,
            server_error_message=spec.server_error_message,
        )
        log_audit_event(request, spec.update_audit_event, account_id)
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).mutations.update_account(
                user_id=current_user["id"],
                account_id=account_id,
                payload=payload,
            ),
        )
        if result is None:
            raise_not_found(request, spec.not_found_message)
        return JSONResponse(content=result)

    @router.delete(f"{base_path}/{{account_id}}")
    async def delete_account(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, spec.delete_audit_event, account_id)
        deleted = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).mutations.delete_account(
                user_id=current_user["id"],
                account_id=account_id,
            ),
        )
        if not deleted:
            raise_not_found(request, spec.not_found_message)
        return JSONResponse(
            content=format_account_delete_result(
                account_id=account_id,
                account_type=spec.account_type,
            ),
        )

    @router.post(f"{base_path}/{{account_id}}/test")
    async def test_account(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, spec.test_audit_event, account_id)
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).queries.test_account(
                user_id=current_user["id"],
                account_id=account_id,
            ),
        )
        return JSONResponse(content=result)

    @router.post(f"{base_path}/{{account_id}}/sync")
    async def sync_account(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload = await read_optional_json_dict_payload_or_raise(
            request,
            invalid_message=spec.invalid_payload_message,
            server_error_message=spec.server_error_message,
        )
        log_audit_event(request, spec.sync_audit_event, account_id)
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.sync_account(
                api_context,
                current_user["id"],
                account_id,
                payload,
            ),
        )
        return JSONResponse(content=result)

    @router.post(f"{base_path}/{{account_id}}/oauth/start")
    async def start_oauth(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, spec.oauth_start_audit_event, account_id)
        try:
            result = await _execute_domain_account_operation(
                request,
                lambda: spec.resolve_accounts(api_context).authorization.start_oauth(
                    user_id=current_user["id"],
                    account_id=account_id,
                ),
            )
            return JSONResponse(content=result)
        except OAuthError as exception:
            raise_invalid_request(request, str(exception))

    @router.get(f"{base_path}/{{account_id}}/oauth/status")
    async def get_oauth_status(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).authorization.get_oauth_status(
                user_id=current_user["id"],
                account_id=account_id,
            ),
        )
        return JSONResponse(content=result)

    @router.post(f"{base_path}/{{account_id}}/oauth/clear")
    async def clear_oauth(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, spec.oauth_clear_audit_event, account_id)
        result = await _execute_domain_account_operation(
            request,
            lambda: spec.resolve_accounts(api_context).authorization.clear_oauth(
                user_id=current_user["id"],
                account_id=account_id,
            ),
        )
        return JSONResponse(content=result)
