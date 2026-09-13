"""SoAI - Encrypted owner-scoped Messaging account repository [backend/database/repositories/users/messaging_accounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.protocols import AsyncContextManagerProtocol
from core.errors.exceptions import ValidationError
from core.messaging.account_models import MessagingAccountCreate, MessagingAccountUpdate
from core.messaging.account_validation import (
    require_messaging_account_id,
    require_messaging_platform,
)
from core.messaging.callback_contracts import (
    require_messaging_callback_ownership_state,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.users.user_id import require_strict_user_id
from core.validation.strings import coerce_optional_trimmed_str
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.messaging_account_deletion import (
    sync_begin_messaging_account_delete,
    sync_finalize_messaging_account_delete,
)
from database.repositories.users.messaging_account_mutation_validation import (
    normalize_messaging_account_create,
    normalize_messaging_account_update,
    prepare_messaging_credentials,
    require_messaging_generation,
    require_messaging_revision,
)
from database.repositories.users.messaging_account_reads import (
    read_deleting_messaging_transport_accounts,
    read_enabled_messaging_transport_accounts,
    read_messaging_account,
    read_messaging_account_credentials,
    read_messaging_accounts,
    read_messaging_bound_conversation_versions,
    read_messaging_transport_account,
    read_reconcilable_messaging_transport_accounts,
)
from database.repositories.users.messaging_account_reconciliation import (
    sync_record_messaging_account_reconciliation,
)
from database.repositories.users.messaging_account_writes import (
    sync_create_messaging_account,
    sync_set_messaging_account_lifecycle_state,
    sync_update_messaging_account,
)
from database.repositories.users.messaging_progress_reads import (
    read_messaging_progress_targets,
)
from database.repositories.users.notifications_value_validation import (
    read_max_notifications_per_user,
)

if TYPE_CHECKING:
    from core.messaging.account_models import (
        MessagingAccountDeleteFence,
        MessagingAccountReconciliationResult,
        MessagingConversationVersion,
        MessagingProgressTarget,
    )
    from core.messaging.callback_contracts import MessagingCallbackOwnershipState
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMessagingAccounts",)


class DatabaseMessagingAccounts:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.fernets = deps.fernet
        self.event_bus = deps.event_bus
        self.config = deps.config
        self._account_lifecycle_locks = TTLAsyncLockRegistry[str](
            TTLAsyncLockRegistryDependencies(),
        )

    def account_lifecycle_lock(
        self,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]:
        return self._account_lifecycle_locks.lock(
            require_messaging_account_id(account_id),
        )

    async def list_accounts(self, user_id: int) -> list[JSONDict]:
        normalized_user_id = require_strict_user_id(user_id)
        return await self.core.reader.execute_read(
            read_messaging_accounts,
            user_id=normalized_user_id,
        )

    async def get_account(self, user_id: int, account_id: str) -> JSONDict | None:
        normalized_user_id = require_strict_user_id(user_id)
        normalized_account_id = require_messaging_account_id(account_id)
        return await self.core.reader.execute_read(
            read_messaging_account,
            user_id=normalized_user_id,
            account_id=normalized_account_id,
        )

    async def get_credentials(self, user_id: int, account_id: str) -> JSONDict | None:
        normalized_user_id = require_strict_user_id(user_id)
        normalized_account_id = require_messaging_account_id(account_id)
        return await self.core.reader.execute_read(
            read_messaging_account_credentials,
            fernets=self.fernets,
            user_id=normalized_user_id,
            account_id=normalized_account_id,
        )

    async def get_transport_account(
        self,
        account_id: str,
        platform: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            read_messaging_transport_account,
            fernets=self.fernets,
            account_id=require_messaging_account_id(account_id),
            platform=require_messaging_platform(platform),
        )

    async def list_enabled_transport_accounts(self, platform: str) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            read_enabled_messaging_transport_accounts,
            fernets=self.fernets,
            platform=require_messaging_platform(platform),
        )

    async def list_deleting_transport_accounts(self) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            read_deleting_messaging_transport_accounts,
            fernets=self.fernets,
        )

    async def list_reconcilable_transport_accounts(self, platform: str) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            read_reconcilable_messaging_transport_accounts,
            fernets=self.fernets,
            platform=require_messaging_platform(platform),
        )

    async def list_bound_conversation_versions(
        self,
        user_id: int,
        account_id: str,
    ) -> tuple[MessagingConversationVersion, ...]:
        return await self.core.reader.execute_read(
            read_messaging_bound_conversation_versions,
            user_id=require_strict_user_id(user_id),
            account_id=require_messaging_account_id(account_id),
        )

    async def list_progress_targets(
        self,
        *,
        active_before_ms: int,
        limit: int,
    ) -> list[MessagingProgressTarget]:
        return await self.core.reader.execute_read(
            read_messaging_progress_targets,
            fernets=self.fernets,
            active_before_ms=active_before_ms,
            limit=limit,
        )

    async def create_account(
        self,
        user_id: int,
        account: MessagingAccountCreate,
    ) -> JSONDict:
        normalized_user_id = require_strict_user_id(user_id)
        normalized_account = normalize_messaging_account_create(account)
        encrypted, fingerprint = prepare_messaging_credentials(
            self.fernets,
            normalized_account.credentials,
        )
        account_id = require_messaging_account_id(normalized_account.account_id)
        model_settings_json = serialize_json_compact_stable_strict(
            normalized_account.model_settings,
        )
        async with self.account_lifecycle_lock(account_id):
            return await self.core.writer.queue_write_operation(
                sync_create_messaging_account,
                normalized_user_id,
                account_id,
                normalized_account,
                encrypted,
                fingerprint,
                model_settings_json,
            )

    async def update_account(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
        account: MessagingAccountUpdate,
    ) -> JSONDict | None:
        normalized_user_id = require_strict_user_id(user_id)
        normalized_account_id = require_messaging_account_id(account_id)
        normalized_revision = require_messaging_revision(expected_revision)
        normalized_account = normalize_messaging_account_update(account)
        encrypted: str | None = None
        fingerprint: str | None = None
        if normalized_account.credentials is not None:
            encrypted, fingerprint = prepare_messaging_credentials(
                self.fernets,
                normalized_account.credentials,
            )
        model_settings_json = serialize_json_compact_stable_strict(
            normalized_account.model_settings,
        )
        async with self.account_lifecycle_lock(normalized_account_id):
            return await self.core.writer.queue_write_operation(
                sync_update_messaging_account,
                normalized_user_id,
                normalized_account_id,
                normalized_revision,
                normalized_account,
                encrypted,
                fingerprint,
                model_settings_json,
            )

    async def set_account_lifecycle_state(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
        *,
        enabled: bool,
    ) -> JSONDict | None:
        if not isinstance(enabled, bool):
            raise ValidationError("Messaging account enabled flag is invalid.")
        normalized_user_id = require_strict_user_id(user_id)
        normalized_account_id = require_messaging_account_id(account_id)
        normalized_revision = require_messaging_revision(expected_revision)
        async with self.account_lifecycle_lock(normalized_account_id):
            return await self.core.writer.queue_write_operation(
                sync_set_messaging_account_lifecycle_state,
                normalized_user_id,
                normalized_account_id,
                normalized_revision,
                "enabled" if enabled else "disabled",
            )

    async def record_reconciliation(
        self,
        *,
        user_id: int,
        account_id: str,
        expected_revision: int,
        lifecycle_generation: int,
        healthy: bool | None,
        callback_fingerprint: str | None,
        ownership_state: MessagingCallbackOwnershipState,
        health_code: str | None,
    ) -> MessagingAccountReconciliationResult | None:
        normalized_health_code = coerce_optional_trimmed_str(health_code)
        if normalized_health_code is not None and len(normalized_health_code) > 120:
            raise ValidationError("Messaging account health code is invalid.")
        result = await self.core.writer.queue_write_operation(
            sync_record_messaging_account_reconciliation,
            require_strict_user_id(user_id),
            require_messaging_account_id(account_id),
            require_messaging_revision(expected_revision),
            require_messaging_generation(lifecycle_generation),
            healthy,
            coerce_optional_trimmed_str(callback_fingerprint),
            require_messaging_callback_ownership_state(ownership_state),
            normalized_health_code,
            read_max_notifications_per_user(self.config),
        )
        if result is not None and result.notification_created:
            notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def begin_delete(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
    ) -> MessagingAccountDeleteFence | None:
        fence = await self.core.writer.queue_write_operation(
            sync_begin_messaging_account_delete,
            require_strict_user_id(user_id),
            require_messaging_account_id(account_id),
            require_messaging_revision(expected_revision),
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return fence

    async def finalize_delete(
        self,
        user_id: int,
        account_id: str,
        lifecycle_generation: int,
    ) -> tuple[MessagingConversationVersion, ...] | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_messaging_account_delete,
            require_strict_user_id(user_id),
            require_messaging_account_id(account_id),
            require_messaging_generation(lifecycle_generation),
        )
