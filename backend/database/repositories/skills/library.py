"""SoAI - Skill library transactional installation and replay [backend/database/repositories/skills/library.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.json import serialize_json_compact_stable_strict
from core.skills.compatibility_profiles import skill_requires_human_invocation
from core.skills.errors import build_skill_error
from core.skills.limits import MAX_INSTALLED_SKILLS, MAX_RETAINED_BYTES
from core.skills.records import SkillPackage
from core.skills.selection import require_skill_upload_id
from core.skills.serialization import skill_manifest_payload
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.skills.retention import (
    sync_reclaim_skill_content,
    sync_reconcile_skill_retention,
)

__all__ = (
    "sync_skill_import_receipt",
    "sync_import_skill",
    "require_skill_library_owner",
    "require_skill_library_capacity",
    "sync_insert_skill_package",
)


def sync_skill_import_receipt(
    connection: sqlite3.Connection,
    user_id: int,
    upload_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        connection.execute(
            """SELECT skill_id, upload_id, upload_digest, package_digest, name,
                  removed_at_ms FROM webui_skills WHERE user_id = ? AND upload_id = ?""",
            (user_id, require_skill_upload_id(upload_id)),
        )
    )
    if row is None:
        return None
    return {
        "skill_id": row["skill_id"],
        "upload_id": row["upload_id"],
        "upload_digest": row["upload_digest"],
        "package_digest": row["package_digest"],
        "name": row["name"],
        "removed": row["removed_at_ms"] is not None,
    }


def sync_import_skill(
    connection: sqlite3.Connection,
    user_id: int,
    upload_id: str,
    package: SkillPackage,
) -> JSONDict:
    require_skill_library_owner(connection, user_id)
    receipt = sync_skill_import_receipt(connection, user_id, upload_id)
    if receipt is not None:
        if receipt["upload_digest"] != package.upload_digest:
            raise build_skill_error("skill_upload_conflict")
        return receipt
    if (
        connection.execute(
            "SELECT 1 FROM webui_skill_import_batches WHERE user_id = ? AND upload_id = ?",
            (user_id, upload_id),
        ).fetchone()
        is not None
    ):
        raise build_skill_error("skill_upload_conflict")
    conflict = connection.execute(
        "SELECT 1 FROM webui_skills WHERE user_id = ? AND name = ? AND removed_at_ms IS NULL",
        (user_id, package.manifest.name),
    ).fetchone()
    if conflict is not None:
        raise build_skill_error("skill_name_conflict")
    sync_reclaim_skill_content(connection, user_id)
    require_skill_library_capacity(connection, user_id, count=1, size_bytes=package.size_bytes)
    timestamp = epoch_ms()
    receipt = sync_insert_skill_package(connection, user_id, upload_id, package, timestamp)
    sync_reconcile_skill_retention(connection, user_id, timestamp, library_changed=True)
    return receipt


def require_skill_library_capacity(
    connection: sqlite3.Connection, user_id: int, *, count: int, size_bytes: int
) -> None:
    installed = connection.execute(
        "SELECT count(*) FROM webui_skills WHERE user_id = ? AND removed_at_ms IS NULL",
        (user_id,),
    ).fetchone()
    retained = connection.execute(
        "SELECT (SELECT coalesce(sum(length(content)), 0) FROM webui_skill_members WHERE user_id = ?) + (SELECT coalesce(sum(length(content)), 0) FROM webui_skill_supporting_members WHERE user_id = ?)",
        (user_id, user_id),
    ).fetchone()
    if installed is None or retained is None:
        raise StateError("Skill capacity query returned no row.")
    if installed[0] + count > MAX_INSTALLED_SKILLS or retained[0] + size_bytes > MAX_RETAINED_BYTES:
        raise build_skill_error("skill_library_full")


def sync_insert_skill_package(
    connection: sqlite3.Connection,
    user_id: int,
    upload_id: str,
    package: SkillPackage,
    timestamp: int,
) -> JSONDict:
    if package.profile is None:
        raise StateError("Skill installation requires a prepared compatibility profile.")
    skill_id = create_prefixed_hex_id("skill")
    manifest = package.manifest
    connection.execute(
        """INSERT INTO webui_skills (
            user_id, skill_id, upload_id, upload_digest, package_digest, name, description,
            manifest_json, disable_model_invocation, user_invocable, size_bytes, created_at_ms,
            profile_json, profile_digest
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            skill_id,
            upload_id,
            package.upload_digest,
            package.digest,
            manifest.name,
            manifest.description,
            serialize_json_compact_stable_strict(skill_manifest_payload(manifest)),
            int(skill_requires_human_invocation(manifest, package.profile)),
            int(manifest.user_invocable),
            package.size_bytes,
            timestamp,
            package.profile.content_json,
            package.profile.digest,
        ),
    )
    connection.executemany(
        """INSERT INTO webui_skill_members
        (user_id, skill_id, path, is_directory, content, digest) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (
                user_id,
                skill_id,
                member.path,
                int(member.is_directory),
                member.content,
                member.digest,
            )
            for member in package.members
        ],
    )
    receipt = sync_skill_import_receipt(connection, user_id, upload_id)
    if receipt is None:
        raise StateError("Skill installation receipt disappeared during its transaction.")
    return receipt


def require_skill_library_owner(connection: sqlite3.Connection, user_id: int) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM webui_users WHERE id = ? AND account_type = 'human'",
            (user_id,),
        ).fetchone()
        is None
    ):
        raise ValidationError("Skill library is unavailable for this account.")
