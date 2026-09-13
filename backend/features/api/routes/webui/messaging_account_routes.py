"""SoAI - Owner Messaging account API routes [backend/features/api/routes/webui/messaging_account_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, status
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import StateError
from core.messaging.account_models import MessagingAccountCreate, MessagingAccountUpdate
from core.messaging.account_validation import require_messaging_platform
from core.runtime.soai_identifiers import create_prefixed_hex_id
from features.api.routes.webui.messaging_account_mutation import (
    build_messaging_authorized_senders,
    resolve_messaging_update_credentials,
    serialize_messaging_credentials,
)
from features.api.routes.webui.messaging_account_post_commit import (
    publish_messaging_settings_authority_changes,
    reconcile_updated_messaging_account,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_not_found
from features.api.runtime.messaging_account_settings import (
    normalize_messaging_account_model_settings,
)
from features.api.schemas.messaging_accounts import (
    MessagingAccountCreateRequest,
    MessagingAccountDeleteRequest,
    MessagingAccountLifecycleRequest,
    MessagingAccountUpdateRequest,
)
from features.messaging.account_callback_reconciliation import (
    preflight_messaging_callback_ownership,
)
from features.messaging.account_lifecycle import execute_messaging_account_delete
from features.messaging.account_principal_validation import resolve_messaging_provider_principal
from features.messaging.account_reconciliation import (
    reconcile_committed_messaging_account,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/messaging/accounts")
    async def list_messaging_accounts(
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        accounts = await api_context.dependencies.database_messaging_accounts.list_accounts(
            current_user["id"],
        )
        return JSONResponse(content=accounts)

    @routers.webui.get("/messaging/accounts/{account_id}")
    async def get_messaging_account(
        request: Request,
        account_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        account = await api_context.dependencies.database_messaging_accounts.get_account(
            current_user["id"],
            account_id,
        )
        if account is None:
            raise_not_found(request, "Messaging account not found.")
        return JSONResponse(content=account)

    @routers.webui.post("/messaging/accounts", status_code=status.HTTP_201_CREATED)
    async def create_messaging_account(
        request: Request,
        payload: MessagingAccountCreateRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        model_settings = await normalize_messaging_account_model_settings(
            request=request,
            api_context=api_context,
            current_user=current_user,
            model_settings=dict(payload.model_settings),
        )
        credentials = serialize_messaging_credentials(payload.credentials)
        account_id = create_prefixed_hex_id("msgacct")
        principal = await resolve_messaging_provider_principal(
            http_client=api_context.dependencies.http_client,
            platform=payload.platform,
            credentials=credentials,
        )
        await preflight_messaging_callback_ownership(
            api_context.dependencies.http_client,
            account={
                "account_id": account_id,
                "platform": payload.platform,
                "credentials": credentials,
            },
            public_origin=api_context.dependencies.config.get_str(
                "SERVER.PUBLIC_ORIGIN",
            )
            or "",
            replace_existing_callback=payload.replace_existing_callback,
        )
        await api_context.dependencies.database_messaging_accounts.create_account(
            current_user["id"],
            MessagingAccountCreate(
                account_id=account_id,
                platform=payload.platform,
                label=payload.label,
                principal_id=principal.principal_id,
                principal_label=principal.principal_label,
                parent_principal_id=principal.parent_principal_id,
                application_principal_id=principal.application_principal_id,
                credentials=credentials,
                model_settings=model_settings,
                locale=payload.locale,
                lifecycle_state="enabled",
                plaintext_secret_replies_enabled=payload.plaintext_secret_replies_enabled,
                accept_messages_from_anyone=payload.accept_messages_from_anyone,
                authorized_senders=build_messaging_authorized_senders(
                    payload.authorized_senders,
                ),
            ),
        )
        try:
            transport_account = (
                await api_context.dependencies.database_messaging_accounts.get_transport_account(
                    account_id,
                    payload.platform,
                )
            )
            if transport_account is None:
                raise_not_found(request, "Messaging account not found after creation.")
            account = await reconcile_committed_messaging_account(
                database_accounts=api_context.dependencies.database_messaging_accounts,
                http_client=api_context.dependencies.http_client,
                public_origin=(
                    api_context.dependencies.config.get_str("SERVER.PUBLIC_ORIGIN") or ""
                ),
                account=transport_account,
                replace_existing_callback=payload.replace_existing_callback,
                refresh_owned_callback=True,
            )
        finally:
            api_context.dependencies.messaging_gateway.request_reconcile()
        return JSONResponse(content=account, status_code=status.HTTP_201_CREATED)

    @routers.webui.put("/messaging/accounts/{account_id}")
    async def update_messaging_account(
        request: Request,
        account_id: str,
        payload: MessagingAccountUpdateRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        repository = api_context.dependencies.database_messaging_accounts
        existing = await repository.get_account(current_user["id"], account_id)
        if existing is None:
            raise_not_found(request, "Messaging account not found.")
        platform = require_messaging_platform(str(existing.get("platform") or ""))
        model_settings = await normalize_messaging_account_model_settings(
            request=request,
            api_context=api_context,
            current_user=current_user,
            model_settings=dict(payload.model_settings),
        )
        credentials, active_credentials, principal = await resolve_messaging_update_credentials(
            request=request,
            api_context=api_context,
            platform=platform,
            existing=existing,
            credentials_payload=payload.credentials,
        )
        if payload.enabled:
            await preflight_messaging_callback_ownership(
                api_context.dependencies.http_client,
                account={
                    "account_id": account_id,
                    "platform": platform,
                    "credentials": active_credentials,
                },
                public_origin=api_context.dependencies.config.get_str(
                    "SERVER.PUBLIC_ORIGIN",
                )
                or "",
                replace_existing_callback=payload.replace_existing_callback,
            )
        updated = await repository.update_account(
            current_user["id"],
            account_id,
            payload.expected_revision,
            MessagingAccountUpdate(
                label=payload.label,
                principal_label=principal.principal_label,
                parent_principal_id=principal.parent_principal_id,
                application_principal_id=principal.application_principal_id,
                credentials=credentials,
                model_settings=model_settings,
                locale=payload.locale,
                lifecycle_state="enabled" if payload.enabled else "disabled",
                plaintext_secret_replies_enabled=payload.plaintext_secret_replies_enabled,
                accept_messages_from_anyone=payload.accept_messages_from_anyone,
                authorized_senders=build_messaging_authorized_senders(
                    payload.authorized_senders,
                ),
            ),
        )
        if updated is None:
            raise_not_found(request, "Messaging account not found.")
        updated = await reconcile_updated_messaging_account(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            account_id=account_id,
            platform=platform,
            replace_existing_callback=payload.replace_existing_callback,
        )
        return JSONResponse(content=updated)

    @routers.webui.post("/messaging/accounts/{account_id}/lifecycle")
    async def set_messaging_account_lifecycle(
        request: Request,
        account_id: str,
        payload: MessagingAccountLifecycleRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        repository = api_context.dependencies.database_messaging_accounts
        existing = await repository.get_account(current_user["id"], account_id)
        if existing is None:
            raise_not_found(request, "Messaging account not found.")
        platform = require_messaging_platform(str(existing.get("platform") or ""))
        if payload.enabled:
            credentials = await repository.get_credentials(current_user["id"], account_id)
            if credentials is None:
                raise StateError("Messaging account credentials are unavailable.")
            await preflight_messaging_callback_ownership(
                api_context.dependencies.http_client,
                account={
                    "account_id": account_id,
                    "platform": platform,
                    "credentials": credentials,
                },
                public_origin=api_context.dependencies.config.get_str(
                    "SERVER.PUBLIC_ORIGIN",
                )
                or "",
                replace_existing_callback=payload.replace_existing_callback,
            )
        changed = await repository.set_account_lifecycle_state(
            current_user["id"],
            account_id,
            payload.expected_revision,
            enabled=payload.enabled,
        )
        if changed is None:
            raise_not_found(request, "Messaging account not found.")
        updated = await reconcile_updated_messaging_account(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            account_id=account_id,
            platform=platform,
            replace_existing_callback=payload.replace_existing_callback,
        )
        return JSONResponse(content=updated)

    @routers.webui.delete(
        "/messaging/accounts/{account_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_messaging_account(
        account_id: str,
        payload: MessagingAccountDeleteRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        repository = api_context.dependencies.database_messaging_accounts
        account = await repository.get_account(current_user["id"], account_id)
        if account is None:
            api_context.dependencies.messaging_gateway.request_reconcile()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        versions = await execute_messaging_account_delete(
            database_accounts=repository,
            api_dependencies=api_context.dependencies,
            http_client=api_context.dependencies.http_client,
            public_origin=(api_context.dependencies.config.get_str("SERVER.PUBLIC_ORIGIN") or ""),
            user_id=current_user["id"],
            account_id=account_id,
            expected_revision=payload.expected_revision,
        )
        api_context.dependencies.messaging_gateway.request_reconcile()
        if versions is not None:
            await publish_messaging_settings_authority_changes(
                api_context=api_context,
                user_id=current_user["id"],
                versions=versions,
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
