"""SoAI - Messaging account post-commit reconciliation and publication [backend/features/api/routes/webui/messaging_account_post_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.events.conversation_publication import publish_conversation_updated
from features.api.runtime.errors import raise_not_found
from features.messaging.account_reconciliation import (
    reconcile_committed_messaging_account,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.account_models import MessagingConversationVersion
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "publish_messaging_settings_authority_changes",
    "reconcile_updated_messaging_account",
)


async def reconcile_updated_messaging_account(
    *,
    request: Request,
    api_context: ApiContext,
    user_id: int,
    account_id: str,
    platform: MessagingPlatform,
    replace_existing_callback: bool,
) -> JSONDict:
    repository = api_context.dependencies.database_messaging_accounts
    try:
        transport_account = await repository.get_transport_account(account_id, platform)
        if transport_account is None:
            raise_not_found(request, "Messaging account not found after update.")
        updated = await reconcile_committed_messaging_account(
            database_accounts=repository,
            http_client=api_context.dependencies.http_client,
            public_origin=(api_context.dependencies.config.get_str("SERVER.PUBLIC_ORIGIN") or ""),
            account=transport_account,
            replace_existing_callback=replace_existing_callback,
            refresh_owned_callback=True,
        )
    finally:
        api_context.dependencies.messaging_gateway.request_reconcile()
    versions = await repository.list_bound_conversation_versions(user_id, account_id)
    await publish_messaging_settings_authority_changes(
        api_context=api_context,
        user_id=user_id,
        versions=versions,
    )
    return updated


async def publish_messaging_settings_authority_changes(
    *,
    api_context: ApiContext,
    user_id: int,
    versions: tuple[MessagingConversationVersion, ...],
) -> None:
    for version in versions:
        await publish_conversation_updated(
            api_context.dependencies.event_bus,
            user_id=user_id,
            conv_id=version.conv_id,
            last_modified_at_ms=version.last_modified_at_ms,
            settings_authority_changed=True,
        )
