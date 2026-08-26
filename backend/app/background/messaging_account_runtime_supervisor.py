"""SoAI - Messaging provider account runtime supervision [backend/app/background/messaging_account_runtime_supervisor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from app.background.messaging_account_runtime_identity import (
    require_messaging_runtime_identity,
)
from app.background.messaging_account_runtime_launch import (
    spawn_discord_account_runtime,
    spawn_webhook_account_runtime,
)
from app.background.messaging_runtime_failure import (
    contain_messaging_runtime_start_failure,
)
from app.background.messaging_runtime_inventory import load_messaging_runtime_inventory
from app.background.messaging_runtime_task_set import (
    MessagingRuntimeSignature,
    MessagingRuntimeTaskSet,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.messaging.account_validation import require_messaging_account_fence
from features.api.runtime.container.types import ApiDependencies

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingIngressProtocol,
    )
    from core.runtime.protocols import (
        RuntimeFlagsViewProtocol,
        RuntimeStateStoreProtocol,
    )
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "MessagingAccountRuntimeSummary",
    "MessagingAccountRuntimeSupervisor",
    "MessagingAccountRuntimeSupervisorDependencies",
)


@dataclass(frozen=True, slots=True)
class MessagingAccountRuntimeSummary:
    account_count: int
    skipped_count: int


@dataclass(frozen=True, slots=True)
class MessagingAccountRuntimeSupervisorDependencies:
    runtime_state: RuntimeStateStoreProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_accounts: DatabaseMessagingAccountsProtocol
    database_ingress: DatabaseMessagingIngressProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    shutdown_event: asyncio.Event

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingAccountRuntimeSupervisorDependencies",
            runtime_state=self.runtime_state,
            runtime_flags=self.runtime_flags,
            http_client=self.http_client,
            database_accounts=self.database_accounts,
            database_ingress=self.database_ingress,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            shutdown_event=self.shutdown_event,
        )


class MessagingAccountRuntimeSupervisor:
    def __init__(self, deps: MessagingAccountRuntimeSupervisorDependencies) -> None:
        self._deps = deps
        self._discord_tasks = MessagingRuntimeTaskSet()
        self._webhook_tasks = MessagingRuntimeTaskSet()

    async def _reconcile_discord_account(
        self,
        account: JSONDict,
        api_dependencies: ApiDependencies,
    ) -> bool:
        identity = require_messaging_runtime_identity(account, "discord")
        account_id = identity.account_id
        signature = identity.signature
        if self._discord_tasks.is_current(
            account_id,
            signature,
            completed_is_healthy=False,
        ):
            return False
        completed_failure = self._discord_tasks.pop_completed_failure(
            account_id,
            signature,
        )
        if completed_failure is not None:
            await contain_messaging_runtime_start_failure(
                task_set=self._discord_tasks,
                api_dependencies=api_dependencies,
                account_id=account_id,
                platform="discord",
                signature=signature,
                exception=completed_failure,
            )
            return True
        if self._discord_tasks.has_task(account_id):
            await self._discord_tasks.stop(account_id, superseded=True)
        if not self._discord_tasks.retry_is_due(account_id, signature):
            return True
        try:
            task = spawn_discord_account_runtime(
                account=account,
                revision=signature.revision,
                lifecycle_generation=signature.lifecycle_generation,
                runtime_flags=self._deps.runtime_flags,
                http_client=self._deps.http_client,
                database_ingress=self._deps.database_ingress,
                api_dependencies=api_dependencies,
                shutdown_event=self._deps.shutdown_event,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
            )
            self._discord_tasks.register(
                account_id=account_id,
                platform="discord",
                signature=signature,
                task=task,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await contain_messaging_runtime_start_failure(
                task_set=self._discord_tasks,
                api_dependencies=api_dependencies,
                account_id=account_id,
                platform="discord",
                signature=signature,
                exception=exception,
            )
            return True
        return False

    async def _reconcile_webhook_account(
        self,
        account: JSONDict,
        api_dependencies: ApiDependencies,
        public_origin: str,
    ) -> bool:
        platform_value = account.get("platform")
        if platform_value not in ("telegram", "whatsapp"):
            raise StateError("Messaging webhook account platform is invalid.")
        platform: MessagingPlatform = platform_value
        identity = require_messaging_runtime_identity(account, platform)
        account_id = identity.account_id
        base_signature = identity.signature
        signature = MessagingRuntimeSignature(
            revision=base_signature.revision,
            lifecycle_generation=base_signature.lifecycle_generation,
            configuration_fingerprint=public_origin,
        )
        if self._webhook_tasks.is_current(
            account_id,
            signature,
            completed_is_healthy=False,
        ):
            return False
        completed_failure = self._webhook_tasks.pop_completed_failure(
            account_id,
            signature,
        )
        if completed_failure is not None:
            await contain_messaging_runtime_start_failure(
                task_set=self._webhook_tasks,
                api_dependencies=api_dependencies,
                account_id=account_id,
                platform=platform,
                signature=signature,
                exception=completed_failure,
            )
            return True
        if self._webhook_tasks.has_task(account_id):
            await self._webhook_tasks.stop(account_id, superseded=True)
        if not self._webhook_tasks.retry_is_due(account_id, signature):
            return True
        try:
            task = spawn_webhook_account_runtime(
                account=account,
                platform=platform,
                revision=signature.revision,
                lifecycle_generation=signature.lifecycle_generation,
                public_origin=public_origin,
                http_client=self._deps.http_client,
                database_accounts=self._deps.database_accounts,
                shutdown_event=self._deps.shutdown_event,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
            )
            self._webhook_tasks.register(
                account_id=account_id,
                platform=platform,
                signature=signature,
                task=task,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await contain_messaging_runtime_start_failure(
                task_set=self._webhook_tasks,
                api_dependencies=api_dependencies,
                account_id=account_id,
                platform=platform,
                signature=signature,
                exception=exception,
            )
            return True
        return False

    async def reconcile(self) -> MessagingAccountRuntimeSummary:
        inventory = await load_messaging_runtime_inventory(
            runtime_state=self._deps.runtime_state,
            runtime_flags=self._deps.runtime_flags,
            database_accounts=self._deps.database_accounts,
        )
        api_dependencies = inventory.api_dependencies
        webhook_accounts = inventory.webhook_accounts
        discord_accounts = inventory.discord_accounts
        active_webhooks: set[str] = set()
        active_discord: set[str] = set()
        skipped_count = 0
        for account in webhook_accounts:
            fence = require_messaging_account_fence(account)
            if fence.platform not in ("telegram", "whatsapp"):
                raise StateError("Messaging webhook account platform is invalid.")
            active_webhooks.add(fence.account_id)
            skipped = await self._reconcile_webhook_account(
                account,
                api_dependencies,
                inventory.public_origin,
            )
            skipped_count += int(skipped)
        for account in discord_accounts:
            fence = require_messaging_account_fence(account)
            if fence.platform != "discord":
                raise StateError("Discord account platform is invalid.")
            active_discord.add(fence.account_id)
            skipped = await self._reconcile_discord_account(account, api_dependencies)
            skipped_count += int(skipped)
        for account_id in self._webhook_tasks.account_ids():
            if account_id not in active_webhooks:
                await self._webhook_tasks.stop(account_id, superseded=False)
        for account_id in self._discord_tasks.account_ids():
            if account_id not in active_discord:
                await self._discord_tasks.stop(account_id, superseded=False)
        return MessagingAccountRuntimeSummary(
            account_count=len(webhook_accounts) + len(discord_accounts),
            skipped_count=skipped_count,
        )

    async def shutdown(self) -> None:
        for account_id in self._discord_tasks.account_ids():
            await self._discord_tasks.stop(account_id, superseded=False)
        for account_id in self._webhook_tasks.account_ids():
            await self._webhook_tasks.stop(account_id, superseded=False)
