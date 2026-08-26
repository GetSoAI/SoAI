"""SoAI - Messaging account runtime task construction [backend/app/background/messaging_account_runtime_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from app.background.messaging_gateway_discord_account import (
    DiscordGatewayAccountDependencies,
    run_discord_gateway_account,
)
from app.background.messaging_gateway_webhook_account import (
    MessagingWebhookAccountDependencies,
    run_messaging_webhook_account,
)
from core.errors.exceptions import StateError
from core.messaging.account_validation import require_messaging_account_fence
from core.messaging.credential_fields import require_messaging_credential
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingIngressProtocol,
    )
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("spawn_discord_account_runtime", "spawn_webhook_account_runtime")


def spawn_discord_account_runtime(
    *,
    account: JSONDict,
    revision: int,
    lifecycle_generation: int,
    runtime_flags: RuntimeFlagsViewProtocol,
    http_client: httpx2.AsyncClient,
    database_ingress: DatabaseMessagingIngressProtocol,
    api_dependencies: ApiDependencies,
    shutdown_event: asyncio.Event,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> asyncio.Task[None]:
    fence = require_messaging_account_fence(account)
    credentials = account.get("credentials")
    if (
        fence.platform != "discord"
        or fence.revision != revision
        or fence.lifecycle_generation != lifecycle_generation
    ):
        raise StateError("Discord account runtime identity is invalid.")
    if not isinstance(credentials, dict):
        raise StateError("Discord account credentials are unavailable.")
    bot_token = require_messaging_credential(
        credentials,
        "bot_token",
        "Discord bot token",
        maximum_length=2048,
    )
    return spawn_tracked_task(
        run_discord_gateway_account(
            deps=DiscordGatewayAccountDependencies(
                runtime_flags=runtime_flags,
                http_client=http_client,
                messaging_ingress=database_ingress,
                api_dependencies=api_dependencies,
            ),
            account_id=fence.account_id,
            user_id=fence.user_id,
            revision=revision,
            lifecycle_generation=lifecycle_generation,
            bot_token=bot_token,
            shutdown_event=shutdown_event,
        ),
        name=f"messaging-discord-{fence.account_id}",
        cancellation_binder=cancellation_binder,
        cancellation_id=create_system_id(
            subsystem="messaging_discord",
            owner=fence.account_id,
            include_random_suffix=True,
        ),
        owner="messaging_gateway",
        metadata={"account_id": fence.account_id, "revision": revision},
        finalizer_tracker=finalizer_tracker,
    )


def spawn_webhook_account_runtime(
    *,
    account: JSONDict,
    platform: MessagingPlatform,
    revision: int,
    lifecycle_generation: int,
    public_origin: str,
    http_client: httpx2.AsyncClient,
    database_accounts: DatabaseMessagingAccountsProtocol,
    shutdown_event: asyncio.Event,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> asyncio.Task[None]:
    fence = require_messaging_account_fence(account)
    if (
        fence.platform != platform
        or fence.revision != revision
        or fence.lifecycle_generation != lifecycle_generation
    ):
        raise StateError("Messaging webhook account identity is invalid.")
    return spawn_tracked_task(
        run_messaging_webhook_account(
            deps=MessagingWebhookAccountDependencies(
                database_accounts=database_accounts,
                http_client=http_client,
                public_origin=public_origin,
            ),
            account=account,
            shutdown_event=shutdown_event,
        ),
        name=f"messaging-webhook-{fence.account_id}",
        cancellation_binder=cancellation_binder,
        cancellation_id=create_system_id(
            subsystem="messaging_webhook",
            owner=fence.account_id,
            include_random_suffix=True,
        ),
        owner="messaging_gateway",
        metadata={"account_id": fence.account_id, "revision": revision},
        finalizer_tracker=finalizer_tracker,
    )
