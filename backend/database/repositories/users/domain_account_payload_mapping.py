"""SoAI - Shared domain account payload mapping [backend/database/repositories/users/domain_account_payload_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from core.timing.epoch import epoch_ms
from core.types.json import JSONValue
from core.users.account_identifier_validation import require_external_account_id
from core.users.account_identifiers import build_random_prefixed_identifier
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.account_validation import optional_epoch_ms, require_user_id
from database.repositories.users.domain_account_storage import insert_user_account_row
from database.repositories.users.internal_protocols import EpochMsReaderProtocol

__all__ = (
    "AccountPayloadFieldMapping",
    "AccountPayloadInsertSpec",
    "build_account_payload_insert_spec",
    "build_account_insert_metadata_row",
    "build_account_payload_row",
    "build_account_payload_updates",
    "insert_account_payload_row",
)

ACCOUNT_INSERT_BASE_COLUMNS = ("id", "user_id", "external_account_id")
ACCOUNT_INSERT_SYNC_COLUMNS = (
    "last_sync_at_ms",
    "last_sync_error",
    "created_at_ms",
    "last_modified_at_ms",
)


@dataclass(frozen=True, slots=True)
class AccountPayloadFieldMapping:
    payload_field: str
    column_name: str
    read_value: Callable[[JSONValue], SQLiteValue]


@dataclass(frozen=True, slots=True)
class AccountPayloadInsertSpec:
    table: str
    account_id_prefix: str
    field_mappings: tuple[AccountPayloadFieldMapping, ...]
    columns: tuple[str, ...]
    require_user_id_value: Callable[[int], int]
    require_external_account_id_value: Callable[[str], str]
    read_optional_epoch_ms: EpochMsReaderProtocol
    create_error_message: str
    created_read_error_message: str


def build_account_insert_metadata_row(
    *,
    account_id_prefix: str,
    user_id: int,
    external_account_id: str,
    payload: dict[str, JSONValue],
    require_user_id_value: Callable[[int], int],
    require_external_account_id_value: Callable[[str], str],
    read_optional_epoch_ms: EpochMsReaderProtocol,
) -> dict[str, SQLiteValue]:
    now_ms = epoch_ms()
    return {
        "id": build_random_prefixed_identifier(account_id_prefix),
        "user_id": require_user_id_value(user_id),
        "external_account_id": require_external_account_id_value(external_account_id),
        "created_at_ms": read_optional_epoch_ms(payload.get("created_at_ms"), label="created_at_ms")
        or now_ms,
        "last_modified_at_ms": read_optional_epoch_ms(
            payload.get("last_modified_at_ms"),
            label="last_modified_at_ms",
        )
        or now_ms,
    }


def build_account_payload_row(
    payload: dict[str, JSONValue],
    field_mappings: tuple[AccountPayloadFieldMapping, ...],
) -> dict[str, SQLiteValue]:
    row: dict[str, SQLiteValue] = {}
    for field_mapping in field_mappings:
        row[field_mapping.column_name] = field_mapping.read_value(
            payload.get(field_mapping.payload_field),
        )
    return row


def build_account_payload_updates(
    updates: dict[str, JSONValue],
    field_mappings: tuple[AccountPayloadFieldMapping, ...],
) -> dict[str, SQLiteValue]:
    mappings_by_field = {
        field_mapping.payload_field: field_mapping for field_mapping in field_mappings
    }
    mapped_updates: dict[str, SQLiteValue] = {"last_modified_at_ms": epoch_ms()}
    for payload_field, value in updates.items():
        field_mapping = mappings_by_field.get(payload_field)
        if field_mapping is None:
            continue
        mapped_updates[field_mapping.column_name] = field_mapping.read_value(value)
    return mapped_updates


def build_account_payload_insert_spec(
    *,
    table: str,
    account_id_prefix: str,
    field_mappings: tuple[AccountPayloadFieldMapping, ...],
    domain_columns: tuple[str, ...],
    create_error_message: str,
    created_read_error_message: str,
) -> AccountPayloadInsertSpec:
    return AccountPayloadInsertSpec(
        table=table,
        account_id_prefix=account_id_prefix,
        field_mappings=field_mappings,
        columns=(*ACCOUNT_INSERT_BASE_COLUMNS, *domain_columns, *ACCOUNT_INSERT_SYNC_COLUMNS),
        require_user_id_value=require_user_id,
        require_external_account_id_value=require_external_account_id,
        read_optional_epoch_ms=optional_epoch_ms,
        create_error_message=create_error_message,
        created_read_error_message=created_read_error_message,
    )


def insert_account_payload_row(
    conn: sqlite3.Connection,
    spec: AccountPayloadInsertSpec,
    user_id: int,
    external_account_id: str,
    payload: dict[str, JSONValue],
) -> SQLiteRowDict:
    row: SQLiteRowDict = build_account_insert_metadata_row(
        account_id_prefix=spec.account_id_prefix,
        user_id=user_id,
        external_account_id=external_account_id,
        payload=payload,
        require_user_id_value=spec.require_user_id_value,
        require_external_account_id_value=spec.require_external_account_id_value,
        read_optional_epoch_ms=spec.read_optional_epoch_ms,
    )
    row.update(build_account_payload_row(payload, spec.field_mappings))
    return insert_user_account_row(
        conn,
        table=spec.table,
        row=row,
        columns=spec.columns,
        create_error_message=spec.create_error_message,
        created_read_error_message=spec.created_read_error_message,
    )
