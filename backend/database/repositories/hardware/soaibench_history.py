"""SoAI - Database SoAIBench history read queries [backend/database/repositories/hardware/soaibench_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.repositories.hardware.soaibench_rows import (
    RUN_COLUMNS,
    identity_text_or_empty,
    materialize_row,
    with_history_match,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "list_soaibench_history_export_query",
    "list_soaibench_history_query",
    "list_soaibench_recent_for_user_query",
)


async def list_soaibench_history_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    identity: JSONDict,
    limit: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        _history_query_sql(limit=True),
        (*_history_query_parameters(user_id=user_id, identity=identity), _history_limit(limit)),
    )
    return [with_history_match(materialize_row(row), identity) for row in rows]


async def list_soaibench_history_export_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    identity: JSONDict,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        _history_query_sql(limit=False),
        _history_query_parameters(user_id=user_id, identity=identity),
    )
    return [with_history_match(materialize_row(row), identity) for row in rows]


async def list_soaibench_recent_for_user_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    limit: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"SELECT {RUN_COLUMNS} FROM hardware_gpu_soaibench_runs WHERE created_by_user_id = ? ORDER BY started_at_ms DESC LIMIT ?",
        (int(user_id), max(1, min(100, int(limit)))),
    )
    return [materialize_row(row) for row in rows]


def _history_query_sql(*, limit: bool) -> str:
    suffix = " LIMIT ?" if limit else ""
    return (
        f"SELECT {RUN_COLUMNS} FROM hardware_gpu_soaibench_runs "
        "WHERE created_by_user_id = ? AND "
        "("
        "(? != '' AND gpu_uuid IS NOT NULL AND gpu_uuid = ?) "
        "OR ("
        "? = '' "
        "AND ? != '' AND gpu_model_key IS NOT NULL AND gpu_model_key = ? "
        "AND (? = '' OR vendor = ?) "
        "AND ("
        "(? != '' AND device_id = ?) "
        "OR (? != '' AND pci_bdf IS NOT NULL AND pci_bdf = ?)"
        ")"
        ")"
        ") "
        f"ORDER BY started_at_ms DESC{suffix}"
    )


def _history_query_parameters(
    *,
    user_id: int,
    identity: JSONDict,
) -> tuple[int, str, str, str, str, str, str, str, str, str, str, str]:
    gpu_uuid = identity_text_or_empty(identity.get("gpu_uuid"))
    model_key = "" if gpu_uuid else identity_text_or_empty(identity.get("gpu_model_key"))
    vendor = "" if gpu_uuid else identity_text_or_empty(identity.get("vendor"))
    device_id = "" if gpu_uuid else identity_text_or_empty(identity.get("device_id"))
    pci_bdf = "" if gpu_uuid else identity_text_or_empty(identity.get("pci_bdf"))
    return (
        int(user_id),
        gpu_uuid,
        gpu_uuid,
        gpu_uuid,
        model_key,
        model_key,
        vendor,
        vendor,
        device_id,
        device_id,
        pci_bdf,
        pci_bdf,
    )


def _history_limit(limit: int) -> int:
    return max(1, min(100, int(limit)))
