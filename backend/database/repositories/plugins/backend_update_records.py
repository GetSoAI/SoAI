"""SoAI - Transactional backend update advisory records [backend/database/repositories/plugins/backend_update_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import replace

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.plugins.backend_update_records import (
    BACKEND_UPDATE_CONTAINMENT_REQUIRED,
    BackendAutoAttempt,
    BackendUpdateIdentity,
    BackendUpdateRecord,
)
from core.runtime.soai_identifiers import create_system_id
from core.types.json import JSONDict
from core.validation.strict_numbers import (
    require_int_in_range_strict,
    require_optional_non_negative_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text
from database.core.query_execution import query_one_to_dict, query_to_dicts, sync_fetch_one_as_dict
from database.core.read_transaction import run_read_transaction
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.plugins.catalog_reads import get_all_listable_plugins_query

__all__ = (
    "get_backend_update_query",
    "get_backend_updates_query",
    "get_backend_update_catalog_query",
    "sync_materialize_backend_update",
    "sync_commit_backend_update",
    "sync_invalidate_backend_update",
    "sync_delete_backend_update",
    "sync_reserve_backend_update",
    "sync_set_backend_update_failure",
    "get_backend_update_cooldown_query",
    "sync_extend_backend_update_cooldown",
)


def _text(row: JSONDict, key: str) -> str:
    return require_canonical_trimmed_json_text(
        row.get(key), error_message=f"Invalid backend update {key}."
    )


def _nullable_text(row: JSONDict, key: str) -> str | None:
    return None if row.get(key) is None else _text(row, key)


def _decode(row: JSONDict) -> BackendUpdateRecord:
    plugin_name = _text(row, "plugin_name")
    identity = BackendUpdateIdentity(
        plugin_name,
        _text(row, "package_hash"),
        _nullable_text(row, "configuration_hash"),
        _text(row, "backend_variant_id"),
    )
    status = row.get("status")
    if status not in ("check_pending", "current", "update_available", "check_failed"):
        raise ValidationError("Invalid backend update status.")
    attempt = None
    if row.get("auto_request_id") is not None:
        attempt = BackendAutoAttempt(
            _text(row, "auto_request_id"),
            BackendUpdateIdentity(
                plugin_name,
                _text(row, "auto_package_hash"),
                _nullable_text(row, "auto_configuration_hash"),
                _text(row, "auto_backend_variant_id"),
            ),
        )
    elif any(
        row.get(key) is not None
        for key in ("auto_package_hash", "auto_configuration_hash", "auto_backend_variant_id")
    ):
        raise ValidationError("Incomplete backend update reservation.")
    return BackendUpdateRecord(
        identity=identity,
        status=status,
        check_id=_text(row, "check_id"),
        current_version=_nullable_text(row, "current_version"),
        latest_version=_nullable_text(row, "latest_version"),
        checked_at_ms=require_optional_non_negative_int_strict(
            row.get("checked_at_ms"), error_message="Invalid backend check timestamp."
        ),
        failure_code=_nullable_text(row, "failure_code"),
        auto_attempt=attempt,
        auto_update_failed=bool(
            require_int_in_range_strict(
                row.get("auto_update_failed"),
                minimum=0,
                maximum=1,
                error_message="Invalid automatic update failure flag.",
            )
        ),
    )


async def get_backend_updates_query(
    database: aiosqlite.Connection,
) -> dict[str, BackendUpdateRecord]:
    rows = await query_to_dicts(
        database, "SELECT * FROM plugin_backend_updates ORDER BY plugin_name"
    )
    records = [_decode(sqlite_row_dict_to_json_dict(row)) for row in rows]
    return {record.identity.plugin_name: record for record in records}


async def get_backend_update_query(
    database: aiosqlite.Connection, plugin_name: str
) -> BackendUpdateRecord | None:
    row = await query_one_to_dict(
        database, "SELECT * FROM plugin_backend_updates WHERE plugin_name = ?", (plugin_name,)
    )
    return _decode(sqlite_row_dict_to_json_dict(row)) if row is not None else None


def _get(connection: sqlite3.Connection, plugin_name: str) -> BackendUpdateRecord | None:
    row = sync_fetch_one_as_dict(
        connection.execute(
            "SELECT * FROM plugin_backend_updates WHERE plugin_name = ?", (plugin_name,)
        )
    )
    return _decode(sqlite_row_dict_to_json_dict(row)) if row is not None else None


def _generation() -> str:
    return create_system_id(subsystem="backend-update", include_random_suffix=True)


def sync_materialize_backend_update(
    connection: sqlite3.Connection, identity: BackendUpdateIdentity
) -> BackendUpdateRecord:
    existing = _get(connection, identity.plugin_name)
    if existing is not None and existing.identity == identity:
        return existing
    if existing is not None and existing.failure_code == BACKEND_UPDATE_CONTAINMENT_REQUIRED:
        raise StateError("Backend worker containment must complete before identity changes.")
    pending = BackendUpdateRecord(identity, "check_pending", _generation())
    if existing is None:
        connection.execute(
            "INSERT INTO plugin_backend_updates(plugin_name, package_hash, configuration_hash, backend_variant_id, status, check_id) VALUES (?, ?, ?, ?, 'check_pending', ?)",
            (
                identity.plugin_name,
                identity.package_hash,
                identity.configuration_hash,
                identity.backend_variant_id,
                pending.check_id,
            ),
        )
    else:
        pending = replace(
            pending,
            auto_attempt=existing.auto_attempt,
            auto_update_failed=existing.auto_update_failed,
        )
        cursor = connection.execute(
            "UPDATE plugin_backend_updates SET package_hash=?, configuration_hash=?, backend_variant_id=?, status='check_pending', check_id=?, current_version=NULL, latest_version=NULL, checked_at_ms=NULL, failure_code=NULL WHERE plugin_name=? AND check_id=?",
            (
                identity.package_hash,
                identity.configuration_hash,
                identity.backend_variant_id,
                pending.check_id,
                identity.plugin_name,
                existing.check_id,
            ),
        )
        if cursor.rowcount != 1:
            raise StateError("Backend update identity materialization was superseded.")
    return pending


def sync_commit_backend_update(
    connection: sqlite3.Connection, expected: BackendUpdateRecord, result: BackendUpdateRecord
) -> bool:
    if expected.identity != result.identity or expected.check_id == result.check_id:
        raise ValidationError(
            "Backend check commit requires the captured identity and a new generation."
        )
    _get(connection, expected.identity.plugin_name)
    identity = expected.identity
    cursor = connection.execute(
        "UPDATE plugin_backend_updates SET status=?, check_id=?, current_version=?, latest_version=?, checked_at_ms=?, failure_code=? WHERE plugin_name=? AND check_id=? AND package_hash=? AND configuration_hash IS ? AND backend_variant_id=?",
        (
            result.status,
            result.check_id,
            result.current_version,
            result.latest_version,
            result.checked_at_ms,
            result.failure_code,
            identity.plugin_name,
            expected.check_id,
            identity.package_hash,
            identity.configuration_hash,
            identity.backend_variant_id,
        ),
    )
    return cursor.rowcount == 1


def sync_invalidate_backend_update(connection: sqlite3.Connection, plugin_name: str) -> bool:
    existing = _get(connection, plugin_name)
    if existing is None:
        return False
    if existing.failure_code == BACKEND_UPDATE_CONTAINMENT_REQUIRED:
        raise StateError("Backend worker containment must complete before invalidation.")
    cursor = connection.execute(
        "UPDATE plugin_backend_updates SET status='check_pending', check_id=?, current_version=NULL, latest_version=NULL, checked_at_ms=NULL, failure_code=NULL WHERE plugin_name=? AND check_id=?",
        (_generation(), plugin_name, existing.check_id),
    )
    return cursor.rowcount == 1


def sync_delete_backend_update(connection: sqlite3.Connection, plugin_name: str) -> None:
    existing = _get(connection, plugin_name)
    if existing is not None and existing.failure_code == BACKEND_UPDATE_CONTAINMENT_REQUIRED:
        raise StateError("Backend worker containment must complete before removal.")
    connection.execute("DELETE FROM plugin_backend_updates WHERE plugin_name=?", (plugin_name,))


def sync_reserve_backend_update(
    connection: sqlite3.Connection, expected: BackendUpdateRecord, attempt: BackendAutoAttempt
) -> bool:
    if expected.identity != attempt.identity:
        raise ValidationError("Backend update reservation identity changed.")
    existing = _get(connection, attempt.identity.plugin_name)
    if (
        existing is None
        or existing != expected
        or (
            existing.auto_attempt is not None
            and existing.auto_attempt.identity.package_hash == attempt.identity.package_hash
        )
    ):
        return False
    identity = attempt.identity
    cursor = connection.execute(
        "UPDATE plugin_backend_updates SET auto_request_id=?, auto_package_hash=?, auto_configuration_hash=?, auto_backend_variant_id=?, auto_update_failed=0 WHERE plugin_name=? AND check_id=? AND package_hash=? AND configuration_hash IS ? AND backend_variant_id=? AND auto_request_id IS ?",
        (
            attempt.request_id,
            identity.package_hash,
            identity.configuration_hash,
            identity.backend_variant_id,
            identity.plugin_name,
            expected.check_id,
            identity.package_hash,
            identity.configuration_hash,
            identity.backend_variant_id,
            expected.auto_attempt.request_id if expected.auto_attempt else None,
        ),
    )
    return cursor.rowcount == 1


def sync_set_backend_update_failure(
    connection: sqlite3.Connection, attempt: BackendAutoAttempt, failed: bool
) -> bool:
    _get(connection, attempt.identity.plugin_name)
    identity = attempt.identity
    cursor = connection.execute(
        "UPDATE plugin_backend_updates SET auto_update_failed=? WHERE plugin_name=? AND auto_request_id=? AND auto_package_hash=? AND auto_configuration_hash IS ? AND auto_backend_variant_id=?",
        (
            int(failed),
            identity.plugin_name,
            attempt.request_id,
            identity.package_hash,
            identity.configuration_hash,
            identity.backend_variant_id,
        ),
    )
    return cursor.rowcount == 1


async def get_backend_update_cooldown_query(database: aiosqlite.Connection) -> int | None:
    row = await query_one_to_dict(
        database, "SELECT not_before_ms FROM plugin_backend_update_network_policy WHERE singleton=1"
    )
    if row is None:
        raise ValidationError("Backend update network policy is missing.")
    return require_optional_non_negative_int_strict(
        sqlite_row_dict_to_json_dict(row)["not_before_ms"],
        error_message="Invalid backend update cooldown.",
    )


def sync_extend_backend_update_cooldown(connection: sqlite3.Connection, not_before_ms: int) -> None:
    require_optional_non_negative_int_strict(
        not_before_ms, error_message="Invalid backend update cooldown."
    )
    cursor = connection.execute(
        "UPDATE plugin_backend_update_network_policy SET not_before_ms=MAX(COALESCE(not_before_ms,0),?) WHERE singleton=1",
        (not_before_ms,),
    )
    if cursor.rowcount != 1:
        raise ValidationError("Backend update network policy is missing.")


async def get_backend_update_catalog_query(
    database: aiosqlite.Connection,
) -> tuple[list[JSONDict], dict[str, BackendUpdateRecord]]:
    async def snapshot(
        connection: aiosqlite.Connection,
    ) -> tuple[list[JSONDict], dict[str, BackendUpdateRecord]]:
        plugins = await get_all_listable_plugins_query(connection)
        records = await get_backend_updates_query(connection)
        return plugins, records

    return await run_read_transaction(database, snapshot)
