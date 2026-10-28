"""SoAI - Pinned materialization sources and shared resource integrity [backend/database/repositories/skills/materialization_sources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.skills.compatibility_profiles import restore_skill_compatibility_profile
from core.skills.materialization import SkillMaterializationRequest
from core.skills.materialization_files import validate_materialization_inventory
from core.skills.publication_layout import map_skill_publication, skill_profile_publication
from core.skills.records import SkillMember
from database.repositories.skills.content import skill_member_from_row

__all__ = ("sync_project_materialization_sources",)


def sync_project_materialization_sources(
    connection: sqlite3.Connection,
    request: SkillMaterializationRequest,
    members: tuple[SkillMember, ...],
) -> tuple[SkillMember, ...]:
    row = connection.execute(
        "SELECT profile_json, profile_digest FROM webui_skills WHERE user_id=? AND skill_id=?",
        (request.identity.user_id, request.skill_id),
    ).fetchone()
    if row is None:
        raise StateError("Materialization source profile is missing.")
    profile = restore_skill_compatibility_profile(row["profile_json"], row["profile_digest"])
    layout = skill_profile_publication(profile)
    if layout != request.publication or (
        layout is not None and profile.digest != request.profile_digest
    ):
        raise StateError("Materialization source bindings differ from the admitted profile.")
    validate_materialization_inventory(members, request.package_digest)
    if layout is None:
        return members
    supporting = tuple(
        skill_member_from_row(dict(row))
        for row in connection.execute(
            """SELECT support.path, 0 AS is_directory, support.content, support.digest FROM webui_skill_support_bindings AS binding JOIN webui_skill_supporting_members AS support ON support.user_id=binding.user_id AND support.upload_id=binding.upload_id AND support.path=binding.path WHERE binding.user_id=? AND binding.skill_id=? ORDER BY support.path""",
            (request.identity.user_id, request.skill_id),
        ).fetchall()
    )
    if tuple((member.path, member.digest) for member in supporting) != layout.supporting_digests:
        raise StateError("Materialization support bindings failed integrity verification.")
    mapped = map_skill_publication(layout.manifest_path.rpartition("/")[0], members, supporting)
    validate_materialization_inventory(
        mapped, layout.digest, layout.manifest_path, layout.executable_paths
    )
    return mapped
