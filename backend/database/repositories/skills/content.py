"""SoAI - Persisted immutable skill member integrity [backend/database/repositories/skills/content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.compatibility_profiles import (
    restore_skill_compatibility_profile,
    skill_requires_human_invocation,
)
from core.skills.execution import AvailableSkill
from core.skills.records import SkillMember
from core.skills.serialization import restore_skill_manifest, restore_skill_resources
from core.validation.integers import is_strict_int
from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "SKILL_RESOURCE_INDEX_SQL",
    "skill_member_from_row",
    "available_skill_from_row",
)

SKILL_RESOURCE_INDEX_SQL = """(SELECT json_group_array(json_object(
    'path', path, 'is_directory', json(CASE is_directory WHEN 1 THEN 'true' ELSE 'false' END),
    'size_bytes', length(content), 'digest', digest))
    FROM (SELECT path, is_directory, content, digest FROM webui_skill_members
        WHERE user_id = skill.user_id AND skill_id = skill.skill_id ORDER BY path))"""


def skill_member_from_row(row: SQLiteRowDict) -> SkillMember:
    path = row["path"]
    content = row["content"]
    digest = row["digest"]
    directory = row["is_directory"]
    if not isinstance(path, str) or not isinstance(content, bytes) or not isinstance(digest, str):
        raise StateError("Stored skill resource has invalid content or identity.")
    if not is_strict_int(directory) or directory not in (0, 1):
        raise StateError("Stored skill resource has invalid entry type.")
    if directory and content:
        raise StateError("Stored skill directory contains file bytes.")
    require_canonical_sha256_hexdigest(digest, label="Skill resource digest")
    if hashlib.sha256(content).hexdigest() != digest:
        raise StateError("Stored skill resource failed its integrity check.")
    return SkillMember(path, bool(directory), content, digest)


def available_skill_from_row(row: SQLiteRowDict) -> AvailableSkill:
    skill_id = row["skill_id"]
    digest = row["package_digest"]
    if (
        not isinstance(skill_id, str)
        or not isinstance(digest, str)
        or digest != row["retained_digest"]
    ):
        raise StateError("Retained skill identity differs from its admitted snapshot.")
    member = skill_member_from_row(row)
    manifest_json = row["manifest_json"]
    if not isinstance(manifest_json, str):
        raise StateError("Retained skill manifest metadata is missing.")
    try:
        manifest = restore_skill_manifest(
            parse_json_dict(manifest_json, field="retained skill manifest"), member.content
        )
    except ValidationError as exception:
        raise StateError("Retained skill manifest is invalid.") from exception
    profile_json, profile_digest = row["profile_json"], row["profile_digest"]
    if (
        not isinstance(profile_json, str)
        or not isinstance(profile_digest, str)
        or profile_digest != row["retained_profile_digest"]
    ):
        raise StateError("Retained skill profile differs from its admitted snapshot.")
    profile = restore_skill_compatibility_profile(profile_json, profile_digest)
    if member.is_directory or (
        manifest.name != row["name"]
        or int(skill_requires_human_invocation(manifest, profile))
        != row["disable_model_invocation"]
        or int(manifest.user_invocable) != row["user_invocable"]
    ):
        raise StateError("Retained skill restrictions differ from the admitted manifest.")
    resources_json = row["resources"]
    if not isinstance(resources_json, str):
        raise StateError("Retained skill resource inventory is missing.")
    return AvailableSkill(
        skill_id,
        digest,
        manifest,
        restore_skill_resources(parse_json_value(resources_json, field="Skill resources")),
        profile,
    )
