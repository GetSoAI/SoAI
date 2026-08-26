"""SoAI - Durable Messaging account deletion recovery [backend/app/background/messaging_account_deletion_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.events.conversation_publication import publish_conversation_updated
from core.messaging.account_validation import require_messaging_account_fence
from core.validation.strings import coerce_required_non_empty_str
from features.messaging.account_lifecycle import execute_messaging_account_delete

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("resume_messaging_account_deletions",)


async def resume_messaging_account_deletions(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    api_dependencies: ApiDependencies,
    http_client: httpx2.AsyncClient,
    event_bus: EventBusProtocol,
) -> None:
    accounts = await database_accounts.list_deleting_transport_accounts()
    if not accounts:
        return
    public_origin = coerce_required_non_empty_str(
        api_dependencies.config.get_str("SERVER.PUBLIC_ORIGIN"),
        label="SERVER.PUBLIC_ORIGIN",
    )
    for account in accounts:
        fence = require_messaging_account_fence(account)
        versions = await execute_messaging_account_delete(
            database_accounts=database_accounts,
            api_dependencies=api_dependencies,
            http_client=http_client,
            public_origin=public_origin,
            user_id=fence.user_id,
            account_id=fence.account_id,
            expected_revision=fence.revision,
        )
        for version in versions or ():
            await publish_conversation_updated(
                event_bus,
                user_id=fence.user_id,
                conv_id=version.conv_id,
                last_modified_at_ms=version.last_modified_at_ms,
                settings_authority_changed=True,
            )
