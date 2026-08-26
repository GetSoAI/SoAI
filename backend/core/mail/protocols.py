"""SoAI - Mail service protocols [backend/core/mail/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.external_accounts.protocols import LinkedDomainAccountStorageProtocol
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.concurrency.protocols import AsyncContextManagerProtocol
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict

__all__ = (
    "DatabaseMailProtocol",
    "MailRuntimeBindingsProtocol",
    "MailServiceProtocol",
    "MailTransportPreparationProtocol",
)


class DatabaseMailProtocol(LinkedDomainAccountStorageProtocol, Protocol):
    async def upsert_folder(
        self,
        *,
        user_id: int,
        account_id: str,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def list_folders(self, *, user_id: int, account_id: str) -> list[JSONDict]: ...

    async def get_folder(self, *, user_id: int, folder_id: str) -> JSONDict | None: ...

    async def get_folder_by_remote_mailbox(
        self,
        *,
        user_id: int,
        account_id: str,
        remote_mailbox: str,
    ) -> JSONDict | None: ...

    async def delete_folder(self, *, user_id: int, folder_id: str) -> bool: ...

    async def upsert_message(
        self,
        *,
        user_id: int,
        account_id: str,
        folder_id: str,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def list_messages(self, *, user_id: int, folder_id: str) -> list[JSONDict]: ...

    async def get_message(self, *, user_id: int, message_id: str) -> JSONDict | None: ...

    async def get_attachment_part(
        self,
        *,
        user_id: int,
        attachment_id: str,
    ) -> JSONDict | None: ...

    async def replace_message_body(
        self,
        *,
        user_id: int,
        message_id: str,
        body_text: str,
        body_html: str | None,
        total_chars: int,
        parts: list[JSONDict],
    ) -> JSONDict | None: ...

    async def update_message(
        self,
        *,
        user_id: int,
        message_id: str,
        updates: JSONDict,
    ) -> JSONDict | None: ...

    async def delete_message(self, *, user_id: int, message_id: str) -> bool: ...

    async def delete_messages(
        self,
        *,
        user_id: int,
        folder_id: str,
        message_ids: list[str],
    ) -> int: ...

    async def get_backfill_state(self, *, user_id: int, folder_id: str) -> JSONDict | None: ...

    async def update_backfill_state(
        self,
        *,
        user_id: int,
        folder_id: str,
        checkpoint_json: str | None,
        last_backfill_at_ms: int | None,
    ) -> bool: ...


class MailTransportPreparationProtocol(Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    database_mail: DatabaseMailProtocol
    external_accounts: ExternalAccountsServiceProtocol

    def account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class MailRuntimeBindingsProtocol(MailTransportPreparationProtocol, Protocol):
    database_files: DatabaseFilesProtocol
    database_notifications: DatabaseNotificationsProtocol
    storage_manager: StorageManagerProtocol
    mail_blocking_pool: BoundedBlockingPool


class MailServiceProtocol(MailRuntimeBindingsProtocol, Protocol):
    async def shutdown(self) -> None: ...

    async def sync_account(
        self,
        *,
        user_id: int,
        account_id: str,
        folder_id: str | None,
    ) -> JSONDict: ...

    async def list_folders(
        self,
        *,
        user_id: int,
        account_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def list_messages(
        self,
        *,
        user_id: int,
        folder_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def read_message(
        self,
        *,
        user_id: int,
        message_id: str,
        part_id: str | None,
        max_chars: int,
        offset_chars: int,
    ) -> JSONDict: ...

    async def download_attachment(
        self,
        *,
        user_id: int,
        attachment_id: str,
        request_context: RequestContext,
    ) -> JSONDict: ...

    async def remote_search_messages(
        self,
        *,
        user_id: int,
        account_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def backfill_folder(
        self,
        *,
        user_id: int,
        folder_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def compose_message(self, *, user_id: int, payload: JSONDict) -> JSONDict: ...

    async def update_message(
        self,
        *,
        user_id: int,
        message_id: str,
        action: str,
        destination_folder_id: str | None,
    ) -> JSONDict: ...

    async def update_folder(
        self,
        *,
        user_id: int,
        account_id: str,
        action: str,
        folder_id: str | None,
        folder_name: str | None,
    ) -> JSONDict: ...
