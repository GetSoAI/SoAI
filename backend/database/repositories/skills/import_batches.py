"""SoAI - Atomic collection installation and coherent durable receipts [backend/database/repositories/skills/import_batches.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from uuid import UUID, uuid5

import aiosqlite

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_value
from core.skills.collection_staging import read_staged_skill_package
from core.skills.errors import build_skill_error
from core.skills.records import StagedSkillCollection
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.skills.library import (
    require_skill_library_capacity,
    require_skill_library_owner,
    sync_insert_skill_package,
)
from database.repositories.skills.retention import (
    sync_reclaim_skill_content,
    sync_reconcile_skill_retention,
)

__all__ = ("read_skill_import_batch", "sync_skill_import_batch_receipt", "sync_import_skill_batch")

_BATCH_RECEIPT_SQL = """SELECT batch.upload_id, batch.upload_digest,
    (SELECT json_group_array(json_object(
        'skill_id', skill.skill_id, 'upload_id', skill.upload_id,
        'upload_digest', skill.upload_digest, 'package_digest', skill.package_digest,
        'name', skill.name, 'removed', json(CASE WHEN skill.removed_at_ms IS NULL THEN 'false' ELSE 'true' END),
        'source_root', member.source_root)) FROM (
            SELECT * FROM webui_skill_import_batch_members
            WHERE user_id = batch.user_id AND upload_id = batch.upload_id ORDER BY source_root
        ) AS member JOIN webui_skills AS skill
            ON skill.user_id = member.user_id AND skill.skill_id = member.skill_id) AS members
    FROM webui_skill_import_batches AS batch WHERE batch.user_id = ? AND batch.upload_id = ?"""


def sync_skill_import_batch_receipt(
    connection: sqlite3.Connection, user_id: int, upload_id: str
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(connection.execute(_BATCH_RECEIPT_SQL, (user_id, upload_id)))
    return None if row is None else _receipt_payload(row)


async def read_skill_import_batch(
    connection: aiosqlite.Connection, user_id: int, upload_id: str
) -> JSONDict | None:
    row = await query_one_to_dict(connection, _BATCH_RECEIPT_SQL, (user_id, upload_id))
    return None if row is None else _receipt_payload(row)


def _receipt_payload(row: SQLiteRowDict) -> JSONDict:
    payload = sqlite_row_dict_to_json_dict(row)
    return {
        "upload_id": payload["upload_id"],
        "upload_digest": payload["upload_digest"],
        "members": parse_json_value(str(row["members"]), field="skill collection receipt"),
    }


def sync_import_skill_batch(
    connection: sqlite3.Connection, user_id: int, upload_id: str, collection: StagedSkillCollection
) -> JSONDict:
    require_skill_library_owner(connection, user_id)
    receipt = sync_skill_import_batch_receipt(connection, user_id, upload_id)
    if receipt is not None:
        if receipt["upload_digest"] != collection.upload_digest:
            raise build_skill_error("skill_upload_conflict")
        return receipt
    if (
        connection.execute(
            "SELECT 1 FROM webui_skills WHERE user_id = ? AND upload_id = ?", (user_id, upload_id)
        ).fetchone()
        is not None
    ):
        raise build_skill_error("skill_upload_conflict")
    timestamp = epoch_ms()
    if not collection.packages:
        raise StateError("Skill collection installation requires validated members.")
    namespace = UUID(upload_id)
    for package in collection.packages:
        if (
            connection.execute(
                "SELECT 1 FROM webui_skills WHERE user_id = ? AND name = ? AND removed_at_ms IS NULL",
                (user_id, package.manifest.name),
            ).fetchone()
            is not None
        ):
            raise build_skill_error("skill_name_conflict")
        child_id = str(uuid5(namespace, package.source_root))
        if (
            connection.execute(
                "SELECT 1 FROM webui_skills WHERE user_id = ? AND upload_id = ? UNION ALL SELECT 1 FROM webui_skill_import_batches WHERE user_id = ? AND upload_id = ?",
                (user_id, child_id, user_id, child_id),
            ).fetchone()
            is not None
        ):
            raise build_skill_error("skill_upload_conflict")
    sync_reclaim_skill_content(connection, user_id)
    require_skill_library_capacity(
        connection,
        user_id,
        count=len(collection.packages),
        size_bytes=sum(package.size_bytes for package in collection.packages)
        + sum(
            {
                resource.path: resource.size_bytes
                for package in collection.packages
                for resource in package.supporting_resources
            }.values()
        ),
    )
    connection.execute(
        "INSERT INTO webui_skill_import_batches (user_id, upload_id, upload_digest, created_at_ms) VALUES (?, ?, ?, ?)",
        (user_id, upload_id, collection.upload_digest, timestamp),
    )
    for staged_package in collection.packages:
        child_id = str(uuid5(namespace, staged_package.source_root))
        retained_package = read_staged_skill_package(collection, staged_package)
        member = sync_insert_skill_package(
            connection, user_id, child_id, retained_package, timestamp
        )
        connection.execute(
            "INSERT INTO webui_skill_import_batch_members (user_id, upload_id, skill_id, source_root) VALUES (?, ?, ?, ?)",
            (user_id, upload_id, member["skill_id"], staged_package.source_root),
        )
        for supporting in retained_package.supporting_members:
            existing = connection.execute(
                "SELECT digest, content FROM webui_skill_supporting_members WHERE user_id=? AND upload_id=? AND path=?",
                (user_id, upload_id, supporting.path),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO webui_skill_supporting_members VALUES (?, ?, ?, ?, ?)",
                    (user_id, upload_id, supporting.path, supporting.content, supporting.digest),
                )
            elif (
                existing["digest"] != supporting.digest or existing["content"] != supporting.content
            ):
                raise StateError(
                    "Collection supporting resource identity changed during installation."
                )
            connection.execute(
                "INSERT INTO webui_skill_support_bindings VALUES (?, ?, ?, ?)",
                (user_id, member["skill_id"], upload_id, supporting.path),
            )
    sync_reconcile_skill_retention(connection, user_id, timestamp, library_changed=True)
    receipt = sync_skill_import_batch_receipt(connection, user_id, upload_id)
    if receipt is None:
        raise StateError("Committed skill collection receipt is unavailable.")
    return receipt
