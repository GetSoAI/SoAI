"""SoAI - Mail domain service [backend/features/mail/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, override

from core.concurrency.bounded_blocking import shutdown_bounded_pool_executor
from core.concurrency.protocols import (
    AsyncContextManagerProtocol,
    AsyncLockRegistryProtocol,
)
from core.mail.protocols import MailServiceProtocol
from core.types.json import JSONDict
from features.external_accounts.account_locking import acquire_account_lock
from features.mail.dependencies import MailServiceDependencies
from features.mail.mail_backfill import backfill_folder_method
from features.mail.mail_remote_search import remote_search_messages_method
from features.mail.message_attachment_methods import download_attachment_method
from features.mail.message_read_methods import read_message_method
from features.mail.mutation_methods import (
    compose_message_method,
    sync_account_method,
    update_folder_method,
    update_message_method,
)
from features.mail.query_methods import list_folders_method, list_messages_method

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext

__all__ = ("MailService",)


class MailService(MailServiceProtocol):
    def __init__(self, deps: MailServiceDependencies) -> None:
        self.config = deps.config
        self.runtime_flags = deps.runtime_flags
        self.event_bus = deps.event_bus
        self.database_mail = deps.database_mail
        self.database_files = deps.database_files
        self.database_notifications = deps.database_notifications
        self.external_accounts = deps.external_accounts
        self.storage_manager = deps.storage_manager
        self.mail_blocking_pool = deps.mail_blocking_pool
        self._account_locks: AsyncLockRegistryProtocol[tuple[int, str]] = deps.mail_account_locks

    @override
    async def sync_account(
        self,
        *,
        user_id: int,
        account_id: str,
        folder_id: str | None,
    ) -> JSONDict:
        return await sync_account_method(
            self,
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id,
        )

    @override
    async def list_folders(self, *, user_id: int, account_id: str, arguments: JSONDict) -> JSONDict:
        return await list_folders_method(
            self,
            user_id=user_id,
            account_id=account_id,
            arguments=arguments,
        )

    @override
    async def list_messages(self, *, user_id: int, folder_id: str, arguments: JSONDict) -> JSONDict:
        return await list_messages_method(
            self,
            user_id=user_id,
            folder_id=folder_id,
            arguments=arguments,
        )

    @override
    async def read_message(
        self,
        *,
        user_id: int,
        message_id: str,
        part_id: str | None,
        max_chars: int,
        offset_chars: int,
    ) -> JSONDict:
        return await read_message_method(
            self,
            user_id=user_id,
            message_id=message_id,
            part_id=part_id,
            max_chars=max_chars,
            offset_chars=offset_chars,
        )

    @override
    async def download_attachment(
        self,
        *,
        user_id: int,
        attachment_id: str,
        request_context: RequestContext,
    ) -> JSONDict:
        return await download_attachment_method(
            self,
            user_id=user_id,
            attachment_id=attachment_id,
            request_context=request_context,
        )

    @override
    async def remote_search_messages(
        self,
        *,
        user_id: int,
        account_id: str,
        arguments: JSONDict,
    ) -> JSONDict:
        return await remote_search_messages_method(
            self,
            user_id=user_id,
            account_id=account_id,
            arguments=arguments,
        )

    @override
    async def backfill_folder(
        self,
        *,
        user_id: int,
        folder_id: str,
        arguments: JSONDict,
    ) -> JSONDict:
        return await backfill_folder_method(
            self,
            user_id=user_id,
            folder_id=folder_id,
            arguments=arguments,
        )

    @override
    async def compose_message(self, *, user_id: int, payload: JSONDict) -> JSONDict:
        return await compose_message_method(self, user_id=user_id, payload=payload)

    @override
    async def update_message(
        self,
        *,
        user_id: int,
        message_id: str,
        action: str,
        destination_folder_id: str | None,
    ) -> JSONDict:
        return await update_message_method(
            self,
            user_id=user_id,
            message_id=message_id,
            action=action,
            destination_folder_id=destination_folder_id,
        )

    @override
    async def update_folder(
        self,
        *,
        user_id: int,
        account_id: str,
        action: str,
        folder_id: str | None,
        folder_name: str | None,
    ) -> JSONDict:
        return await update_folder_method(
            self,
            user_id=user_id,
            account_id=account_id,
            action=action,
            folder_id=folder_id,
            folder_name=folder_name,
        )

    @override
    def account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]:
        return acquire_account_lock(
            self._account_locks,
            user_id=user_id,
            account_id=account_id,
            label="account_id",
        )

    @override
    async def shutdown(self) -> None:
        shutdown_bounded_pool_executor(self.mail_blocking_pool)
