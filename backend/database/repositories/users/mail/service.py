"""SoAI - Mail repository service [backend/database/repositories/users/mail/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, override

from core.mail.protocols import DatabaseMailProtocol
from core.types.json import JSONDict
from database.repositories.users.domain_account_repository_methods import (
    create_repository_account,
    delete_repository_account,
    get_repository_account,
    list_repository_accounts,
    update_repository_account,
)
from database.repositories.users.mail.accounts import (
    read_mail_account,
    read_mail_accounts,
    sync_create_mail_account,
    sync_delete_mail_account,
    sync_update_mail_account,
)
from database.repositories.users.mail.backfill_methods import (
    get_backfill_state_method,
    update_backfill_state_method,
)
from database.repositories.users.mail.folder_methods import (
    delete_folder_method,
    get_folder_by_remote_mailbox_method,
    get_folder_method,
    list_folders_method,
    upsert_folder_method,
)
from database.repositories.users.mail.message_methods import (
    delete_message_method,
    delete_messages_method,
    get_attachment_part_method,
    get_message_method,
    list_messages_method,
    replace_message_body_method,
    update_message_method,
    upsert_message_method,
)
from database.repositories.users.mail.record_normalization import (
    normalize_mail_account_row,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMail",)


class DatabaseMail(DatabaseMailProtocol):
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config

    @override
    async def list_accounts(self, *, user_id: int) -> list[JSONDict]:
        return await list_repository_accounts(
            self,
            user_id=user_id,
            read_accounts=read_mail_accounts,
            normalize_row=normalize_mail_account_row,
        )

    @override
    async def get_account(self, *, user_id: int, account_id: str) -> JSONDict | None:
        return await get_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            read_account=read_mail_account,
            normalize_row=normalize_mail_account_row,
        )

    @override
    async def create_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        return await create_repository_account(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
            payload=payload,
            create_account=sync_create_mail_account,
            normalize_row=normalize_mail_account_row,
            invalid_message="Created mail account is invalid.",
        )

    @override
    async def update_account(
        self,
        *,
        user_id: int,
        account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None:
        return await update_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            updates=updates,
            update_account=sync_update_mail_account,
            normalize_row=normalize_mail_account_row,
        )

    @override
    async def delete_account(self, *, user_id: int, account_id: str) -> bool:
        return await delete_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            delete_account=sync_delete_mail_account,
        )

    @override
    async def upsert_folder(self, *, user_id: int, account_id: str, payload: JSONDict) -> JSONDict:
        return await upsert_folder_method(
            self,
            user_id=user_id,
            account_id=account_id,
            payload=payload,
        )

    @override
    async def list_folders(self, *, user_id: int, account_id: str) -> list[JSONDict]:
        return await list_folders_method(self, user_id=user_id, account_id=account_id)

    @override
    async def get_folder(self, *, user_id: int, folder_id: str) -> JSONDict | None:
        return await get_folder_method(self, user_id=user_id, folder_id=folder_id)

    @override
    async def get_folder_by_remote_mailbox(
        self,
        *,
        user_id: int,
        account_id: str,
        remote_mailbox: str,
    ) -> JSONDict | None:
        return await get_folder_by_remote_mailbox_method(
            self,
            user_id=user_id,
            account_id=account_id,
            remote_mailbox=remote_mailbox,
        )

    @override
    async def delete_folder(self, *, user_id: int, folder_id: str) -> bool:
        return await delete_folder_method(self, user_id=user_id, folder_id=folder_id)

    @override
    async def upsert_message(
        self,
        *,
        user_id: int,
        account_id: str,
        folder_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        return await upsert_message_method(
            self,
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id,
            payload=payload,
        )

    @override
    async def list_messages(self, *, user_id: int, folder_id: str) -> list[JSONDict]:
        return await list_messages_method(self, user_id=user_id, folder_id=folder_id)

    @override
    async def get_message(self, *, user_id: int, message_id: str) -> JSONDict | None:
        return await get_message_method(self, user_id=user_id, message_id=message_id)

    @override
    async def get_attachment_part(self, *, user_id: int, attachment_id: str) -> JSONDict | None:
        return await get_attachment_part_method(
            self,
            user_id=user_id,
            attachment_id=attachment_id,
        )

    @override
    async def replace_message_body(
        self,
        *,
        user_id: int,
        message_id: str,
        body_text: str,
        body_html: str | None,
        total_chars: int,
        parts: list[JSONDict],
    ) -> JSONDict | None:
        return await replace_message_body_method(
            self,
            user_id=user_id,
            message_id=message_id,
            body_text=body_text,
            body_html=body_html,
            total_chars=total_chars,
            parts=parts,
        )

    @override
    async def update_message(
        self,
        *,
        user_id: int,
        message_id: str,
        updates: JSONDict,
    ) -> JSONDict | None:
        return await update_message_method(
            self,
            user_id=user_id,
            message_id=message_id,
            updates=updates,
        )

    @override
    async def delete_message(self, *, user_id: int, message_id: str) -> bool:
        return await delete_message_method(self, user_id=user_id, message_id=message_id)

    @override
    async def delete_messages(self, *, user_id: int, folder_id: str, message_ids: list[str]) -> int:
        return await delete_messages_method(
            self,
            user_id=user_id,
            folder_id=folder_id,
            message_ids=message_ids,
        )

    @override
    async def get_backfill_state(self, *, user_id: int, folder_id: str) -> JSONDict | None:
        return await get_backfill_state_method(self, user_id=user_id, folder_id=folder_id)

    @override
    async def update_backfill_state(
        self,
        *,
        user_id: int,
        folder_id: str,
        checkpoint_json: str | None,
        last_backfill_at_ms: int | None,
    ) -> bool:
        return await update_backfill_state_method(
            self,
            user_id=user_id,
            folder_id=folder_id,
            checkpoint_json=checkpoint_json,
            last_backfill_at_ms=last_backfill_at_ms,
        )
