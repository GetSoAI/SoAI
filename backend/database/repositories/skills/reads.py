"""SoAI - Coherent owner scoped skill library reads [backend/database/repositories/skills/reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.skills.errors import build_skill_error
from core.skills.limits import skill_library_limits
from core.skills.records import SkillMember
from core.types.json import JSONDict
from database.core.query_execution import query_one_to_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.skills.content import SKILL_RESOURCE_INDEX_SQL, skill_member_from_row

__all__ = (
    "skill_read_library",
    "skill_read_details",
    "skill_read_resource",
    "skill_read_selection",
    "skill_read_import_receipt",
)


async def skill_read_library(connection: aiosqlite.Connection, user_id: int) -> JSONDict:
    row = await query_one_to_dict(
        connection,
        """SELECT
            coalesce((SELECT revision FROM webui_skill_libraries WHERE user_id = owner.id), 0) AS revision,
            ((SELECT coalesce(sum(length(content)), 0) FROM webui_skill_members WHERE user_id = owner.id) + (SELECT coalesce(sum(length(content)), 0) FROM webui_skill_supporting_members WHERE user_id = owner.id)) AS retained_bytes,
            (SELECT json_group_array(json_object(
                'skill_id', skill_id, 'name', name, 'description', description,
                'disable_model_invocation', json(CASE disable_model_invocation WHEN 1 THEN 'true' ELSE 'false' END),
                'user_invocable', json(CASE user_invocable WHEN 1 THEN 'true' ELSE 'false' END),
                'package_digest', package_digest, 'size_bytes', size_bytes, 'created_at_ms', created_at_ms
            )) FROM (SELECT * FROM webui_skills WHERE user_id = owner.id AND removed_at_ms IS NULL ORDER BY name, skill_id)) AS skills
        FROM webui_users AS owner WHERE owner.id = ? AND owner.account_type = 'human'""",
        (user_id,),
    )
    if row is None:
        raise ValidationError("Skill library is unavailable for this account.")
    result = sqlite_row_dict_to_json_dict(row)
    result["limits"] = skill_library_limits()
    result["skills"] = parse_json_value(str(row["skills"]), field="skill library")
    return result


async def skill_read_details(
    connection: aiosqlite.Connection, user_id: int, skill_id: str
) -> JSONDict:
    row = await query_one_to_dict(
        connection,
        f"""SELECT skill_id, name, description, package_digest, manifest_json,
            {SKILL_RESOURCE_INDEX_SQL} AS resources
        FROM webui_skills AS skill WHERE user_id = ? AND skill_id = ? AND removed_at_ms IS NULL""",
        (user_id, skill_id),
    )
    if row is None:
        raise build_skill_error("skill_not_found")
    result = sqlite_row_dict_to_json_dict(row)
    result["manifest"] = parse_json_dict(str(result.pop("manifest_json")), field="skill manifest")
    result["resources"] = parse_json_value(str(row["resources"]), field="skill resources")
    return result


async def skill_read_selection(
    connection: aiosqlite.Connection, user_id: int, conv_id: str
) -> JSONDict:
    row = await query_one_to_dict(
        connection,
        """SELECT id AS conv_id,
            coalesce((SELECT revision FROM webui_conversation_skill_state WHERE user_id = conversation.user_id AND conv_id = conversation.id), 0) AS revision,
            (SELECT json_group_array(skill_id) FROM (
                SELECT skill_id FROM webui_conversation_skills
                WHERE user_id = conversation.user_id AND conv_id = conversation.id ORDER BY skill_id
            )) AS skill_ids
        FROM webui_conversations AS conversation WHERE user_id = ? AND id = ?""",
        (user_id, conv_id),
    )
    if row is None:
        raise ValidationError("Conversation not found or access denied.")
    result = sqlite_row_dict_to_json_dict(row)
    result["skill_ids"] = parse_json_value(str(row["skill_ids"]), field="skill selection")
    return result


async def skill_read_import_receipt(
    connection: aiosqlite.Connection, user_id: int, upload_id: str
) -> JSONDict | None:
    row = await query_one_to_dict(
        connection,
        """SELECT skill_id, upload_id, upload_digest, package_digest, name, removed_at_ms
        FROM webui_skills WHERE user_id = ? AND upload_id = ?""",
        (user_id, upload_id),
    )
    if row is None:
        return None
    result = sqlite_row_dict_to_json_dict(row)
    result["removed"] = result.pop("removed_at_ms") is not None
    return result


async def skill_read_resource(
    connection: aiosqlite.Connection, user_id: int, skill_id: str, path: str
) -> SkillMember:
    row = await query_one_to_dict(
        connection,
        """SELECT member.path, member.is_directory, member.content, member.digest
        FROM webui_skill_members AS member JOIN webui_skills AS skill
        ON skill.user_id = member.user_id AND skill.skill_id = member.skill_id
        WHERE member.user_id = ? AND member.skill_id = ? AND member.path = ? AND skill.removed_at_ms IS NULL""",
        (user_id, skill_id, path),
    )
    if row is None:
        raise build_skill_error("skill_not_found")
    return skill_member_from_row(row)
