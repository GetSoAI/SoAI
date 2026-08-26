"""SoAI - Licensing operation read models [backend/database/repositories/licensing/operation_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import StateError
from core.licensing.storage_records import (
    RecoverableLicensingOperation,
    StoredLicensingOperationResponse,
)
from core.types.json import JSONDict
from database.core.query_execution import query_one_to_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict

LICENSING_OPERATION_PUBLIC_COLUMNS = """operation_id, operation_type, state,
idempotency_key, parent_operation_id, request_digest, edition,
licensed_product_scope, instance_id, activation_id, deployment_id, attempt_count,
last_attempt_at_ms, deactivation_reason, next_retry_at_ms, terminal_code,
created_at_ms, updated_at_ms"""


async def read_latest_operation_query(
    connection: aiosqlite.Connection,
    operation_type: str | None = None,
) -> JSONDict | None:
    if operation_type is None:
        query = f"""SELECT {LICENSING_OPERATION_PUBLIC_COLUMNS}
        FROM licensing_operations ORDER BY updated_at_ms DESC LIMIT 1"""
        parameters: tuple[str, ...] = ()
    else:
        query = f"""SELECT {LICENSING_OPERATION_PUBLIC_COLUMNS}
        FROM licensing_operations WHERE operation_type=?
        ORDER BY updated_at_ms DESC LIMIT 1"""
        parameters = (operation_type,)
    row = await query_one_to_dict(connection, query, parameters)
    return sqlite_row_dict_to_json_dict(row) if row is not None else None


async def read_recoverable_operations_query(
    connection: aiosqlite.Connection,
) -> tuple[RecoverableLicensingOperation, ...]:
    rows = await (
        await connection.execute("""SELECT operation_id, operation_type, state, canonical_request,
            attempt_count, next_retry_at_ms FROM licensing_operations
            WHERE state IN ('prepared', 'sending', 'outcome_unknown', 'reconciling',
            'retry_wait') ORDER BY created_at_ms, operation_id""")
    ).fetchall()
    records: list[RecoverableLicensingOperation] = []
    for row in rows:
        content = row[3]
        if content is not None and not isinstance(content, bytes):
            raise StateError("Stored licensing request content is invalid.")
        records.append(
            RecoverableLicensingOperation(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                content,
                int(row[4]),
                None if row[5] is None else int(row[5]),
            )
        )
    return tuple(records)


async def read_latest_operation_response_query(
    connection: aiosqlite.Connection,
    operation_type: str,
) -> StoredLicensingOperationResponse | None:
    row = await (
        await connection.execute(
            """SELECT operation_type, idempotency_key, request_digest, response_content
            FROM licensing_operations WHERE operation_type=? AND state='succeeded'
            ORDER BY updated_at_ms DESC LIMIT 1""",
            (operation_type,),
        )
    ).fetchone()
    if row is None:
        return None
    if not all(isinstance(value, str) for value in row[:3]) or not isinstance(row[3], bytes):
        raise StateError("Stored licensing operation response is invalid.")
    return StoredLicensingOperationResponse(str(row[0]), str(row[1]), str(row[2]), row[3])


__all__ = (
    "LICENSING_OPERATION_PUBLIC_COLUMNS",
    "read_latest_operation_query",
    "read_latest_operation_response_query",
    "read_recoverable_operations_query",
)
