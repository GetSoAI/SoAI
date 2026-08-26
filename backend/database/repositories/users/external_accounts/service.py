"""SoAI - External account repository service [backend/database/repositories/users/external_accounts/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.external_accounts.read_ops import (
    read_external_account,
    read_external_accounts,
)
from database.repositories.users.external_accounts.record_normalization import (
    normalize_external_account_row,
)
from database.repositories.users.external_accounts.write_ops import (
    sync_create_external_account,
    sync_delete_external_account,
    sync_update_external_account,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseExternalAccounts",)


class DatabaseExternalAccounts:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self.fernet = deps.fernet

    async def list_accounts(
        self,
        *,
        user_id: int,
        decrypt_secrets: bool = False,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        rows = await self.core.reader.execute_read(
            read_external_accounts,
            user_id=user_id,
        )
        return [
            normalized
            for row in rows
            if (
                normalized := normalize_external_account_row(
                    row,
                    fernet=self.fernet,
                    decrypt_secrets=decrypt_secrets,
                )
            )
            is not None
        ]

    async def get_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        decrypt_secrets: bool = False,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        row = await self.core.reader.execute_read(
            read_external_account,
            user_id=user_id,
            external_account_id=external_account_id,
        )
        return normalize_external_account_row(
            row,
            fernet=self.fernet,
            decrypt_secrets=decrypt_secrets,
        )

    async def create_account(
        self,
        *,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        row = await self.core.writer.queue_write_operation(
            partial(
                sync_create_external_account,
                fernet=self.fernet,
                user_id=user_id,
                payload=payload,
            ),
        )
        normalized = normalize_external_account_row(
            row,
            fernet=self.fernet,
            decrypt_secrets=False,
        )
        if normalized is None:
            raise ValidationError("Created external account is invalid.")
        return normalized

    async def update_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        row = await self.core.writer.queue_write_operation(
            partial(
                sync_update_external_account,
                fernet=self.fernet,
                user_id=user_id,
                external_account_id=external_account_id,
                updates=updates,
            ),
        )
        return normalize_external_account_row(
            row,
            fernet=self.fernet,
            decrypt_secrets=False,
        )

    async def delete_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return bool(
            await self.core.writer.queue_write_operation(
                partial(
                    sync_delete_external_account,
                    user_id=user_id,
                    external_account_id=external_account_id,
                ),
            ),
        )
