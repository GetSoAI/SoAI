"""SoAI - Shared repository account method helpers [backend/database/repositories/users/domain_account_repository_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, Mapping

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from database.core.flags import FEATURE_AUTH
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.internal_protocols import (
    DatabaseMessagesCoreOwnerProtocol,
)

__all__ = (
    "create_repository_account",
    "delete_repository_account",
    "get_repository_account",
    "list_repository_accounts",
    "update_repository_account",
)


async def list_repository_accounts(
    repository: DatabaseMessagesCoreOwnerProtocol,
    *,
    user_id: int,
    read_accounts: Callable[..., Awaitable[list[SQLiteRowDict]]],
    normalize_row: Callable[[Mapping[str, SQLiteValue] | None], JSONDict | None],
) -> list[JSONDict]:
    repository.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await repository.core.reader.execute_read(read_accounts, user_id=user_id)
    return [normalized for row in rows if (normalized := normalize_row(row))]


async def get_repository_account(
    repository: DatabaseMessagesCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    read_account: Callable[..., Awaitable[SQLiteRowDict | None]],
    normalize_row: Callable[[Mapping[str, SQLiteValue] | None], JSONDict | None],
) -> JSONDict | None:
    repository.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await repository.core.reader.execute_read(
        read_account,
        user_id=user_id,
        account_id=account_id,
    )
    return normalize_row(row)


async def create_repository_account(
    repository: DatabaseMessagesCoreOwnerProtocol,
    *,
    user_id: int,
    external_account_id: str,
    payload: JSONDict,
    create_account: Callable[..., SQLiteRowDict],
    normalize_row: Callable[[Mapping[str, SQLiteValue] | None], JSONDict | None],
    invalid_message: str,
) -> JSONDict:
    repository.core.features.ensure_feature_enabled(FEATURE_AUTH)

    def write_create(connection: sqlite3.Connection) -> SQLiteRowDict:
        return create_account(
            connection,
            user_id=user_id,
            external_account_id=external_account_id,
            payload=payload,
        )

    row = await repository.core.writer.queue_write_operation(
        write_create,
    )
    normalized = normalize_row(row)
    if normalized is None:
        raise StateError(invalid_message)
    return normalized


async def update_repository_account(
    repository: DatabaseMessagesCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    updates: JSONDict,
    update_account: Callable[..., SQLiteRowDict | None],
    normalize_row: Callable[[Mapping[str, SQLiteValue] | None], JSONDict | None],
) -> JSONDict | None:
    repository.core.features.ensure_feature_enabled(FEATURE_AUTH)

    def write_update(connection: sqlite3.Connection) -> SQLiteRowDict | None:
        return update_account(
            connection,
            user_id=user_id,
            account_id=account_id,
            updates=updates,
        )

    row = await repository.core.writer.queue_write_operation(
        write_update,
    )
    return normalize_row(row)


async def delete_repository_account(
    repository: DatabaseMessagesCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    delete_account: Callable[..., bool],
) -> bool:
    repository.core.features.ensure_feature_enabled(FEATURE_AUTH)

    def write_delete(connection: sqlite3.Connection) -> bool:
        return delete_account(
            connection,
            user_id=user_id,
            account_id=account_id,
        )

    return bool(
        await repository.core.writer.queue_write_operation(
            write_delete,
        ),
    )
