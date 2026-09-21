"""SoAI - Durable SoAIBench publication ledger operations [backend/database/repositories/hardware/soaibench_publications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONDict
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.hardware.soaibench_installation import (
    sync_get_or_create_soaibench_installation_id,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "get_soaibench_publication_query",
    "sync_finish_soaibench_publication",
    "sync_prepare_soaibench_publication",
)

PUBLICATION_COLUMNS = (
    "run_id, created_by_user_id, installation_id, canonical_submission_json, "
    "state, prepared_at_ms, published_at_ms, receipt_json"
)


async def get_soaibench_publication_query(
    database: aiosqlite.Connection,
    user_id: int,
    run_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"SELECT {PUBLICATION_COLUMNS} FROM hardware_gpu_soaibench_publications WHERE created_by_user_id=? AND run_id=?",
        (int(user_id), run_id),
    )
    return _materialize(row)


def sync_prepare_soaibench_publication(
    connection: sqlite3.Connection,
    run_id: str,
    user_id: int,
    canonical_submission_json: str,
    prepared_at_ms: int,
) -> JSONDict:
    installation_id = sync_get_or_create_soaibench_installation_id(connection)
    connection.execute(
        """
        INSERT INTO hardware_gpu_soaibench_publications (
            run_id, created_by_user_id, installation_id, canonical_submission_json,
            state, prepared_at_ms,
            published_at_ms, receipt_json
        ) VALUES (?, ?, ?, ?, 'prepared', ?, NULL, NULL)
        ON CONFLICT(run_id) DO NOTHING
        """,
        (
            run_id,
            int(user_id),
            installation_id,
            canonical_submission_json,
            int(prepared_at_ms),
        ),
    )
    return _require_publication(connection, user_id, run_id)


def sync_finish_soaibench_publication(
    connection: sqlite3.Connection,
    run_id: str,
    user_id: int,
    receipt_json: str,
    published_at_ms: int,
) -> JSONDict:
    connection.execute(
        """
        UPDATE hardware_gpu_soaibench_publications
        SET state='published', published_at_ms=?, receipt_json=?
        WHERE run_id=? AND created_by_user_id=? AND state='prepared'
        """,
        (int(published_at_ms), receipt_json, run_id, int(user_id)),
    )
    return _require_publication(connection, user_id, run_id)


def _require_publication(
    connection: sqlite3.Connection,
    user_id: int,
    run_id: str,
) -> JSONDict:
    cursor = connection.execute(
        f"SELECT {PUBLICATION_COLUMNS} FROM hardware_gpu_soaibench_publications WHERE created_by_user_id=? AND run_id=?",
        (int(user_id), run_id),
    )
    publication = _materialize(sync_fetch_one_as_dict(cursor))
    if publication is None:
        raise StateError("SoAIBench publication ledger mutation did not produce a row.")
    return publication


def _materialize(row: SQLiteRowDict | None) -> JSONDict | None:
    if row is None:
        return None
    payload = sqlite_row_dict_to_json_dict(row)
    receipt_json = payload.pop("receipt_json", None)
    payload["receipt"] = (
        None
        if receipt_json is None
        else parse_json_dict(
            str(receipt_json),
            field="SoAIBench publication receipt",
            reject_duplicate_keys=True,
        )
    )
    return payload
