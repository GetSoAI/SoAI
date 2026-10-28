"""SoAI - Coherent retained skill availability for admitted execution [backend/database/repositories/skills/execution_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.runtime.boot_id import get_boot_id
from core.skills.execution import AvailableSkill, SkillExecutionIdentity, SkillSnapshot
from core.skills.records import SkillMember
from core.validation.integers import is_strict_int
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.skills.content import (
    SKILL_RESOURCE_INDEX_SQL,
    available_skill_from_row,
    skill_member_from_row,
)
from database.repositories.users.conversation_input_queries import (
    CONVERSATION_INPUT_ACTIVE_CLAIM_SQL,
)

__all__ = (
    "read_execution_skill_snapshot",
    "read_execution_skill_resource",
    "execution_skill_members_sql",
)


def execution_skill_members_sql(*, supporting: bool = False) -> str:
    member_join = "JOIN webui_skill_members AS member ON member.user_id = skill.user_id AND member.skill_id = skill.skill_id"
    directory = "member.is_directory"
    if supporting:
        member_join = """JOIN webui_skill_support_bindings AS binding ON binding.user_id=skill.user_id AND binding.skill_id=skill.skill_id
            JOIN webui_skill_supporting_members AS member ON member.user_id=binding.user_id AND member.upload_id=binding.upload_id AND member.path=binding.path"""
        directory = "0 AS is_directory"
    return f"""SELECT member.path, {directory}, member.content, member.digest
            FROM webui_agent_turns AS turn
            JOIN webui_skill_turn_checkpoints AS checkpoint
              ON checkpoint.user_id = turn.user_id AND checkpoint.conv_id = turn.conv_id
              AND checkpoint.turn_id = turn.turn_id
            JOIN webui_skill_snapshot_members AS snapshot
              ON snapshot.user_id = checkpoint.user_id AND snapshot.conv_id = checkpoint.conv_id
              AND snapshot.input_id = checkpoint.input_id
            JOIN webui_skills AS skill ON skill.user_id = snapshot.user_id AND skill.skill_id = snapshot.skill_id
            {member_join}
            JOIN json_each(checkpoint.activation_json, '$.active_skills') AS activation
              ON json_extract(activation.value, '$.skill_id') = skill.skill_id
              AND json_extract(activation.value, '$.package_digest') = snapshot.package_digest
            WHERE turn.user_id = ? AND turn.conv_id = ? AND turn.turn_id = ?
              AND turn.execution_token = ? AND turn.server_boot_id = ? AND turn.status = 'running'
              AND checkpoint.input_id = ? AND skill.skill_id = ? AND (? IS NULL OR member.path = ?)
              AND skill.package_digest = snapshot.package_digest
              AND skill.profile_digest = snapshot.profile_digest
              AND (turn.parent_turn_id IS NOT NULL OR EXISTS ({CONVERSATION_INPUT_ACTIVE_CLAIM_SQL}))"""


async def read_execution_skill_snapshot(
    connection: aiosqlite.Connection, user_id: int, conv_id: str, input_id: str
) -> SkillSnapshot:
    rows = await query_to_dicts(
        connection,
        f"""SELECT snapshot.root_input_id, snapshot.selection_revision,
            membership.skill_id, membership.package_digest, membership.explicit_ordinal,
            membership.profile_digest, skill.profile_digest AS retained_profile_digest, skill.profile_json,
            membership.invocation_arguments,
            skill.package_digest AS retained_digest, skill.name,
            skill.disable_model_invocation, skill.user_invocable, skill.manifest_json,
            manifest.path, manifest.is_directory, manifest.content, manifest.digest,
            {SKILL_RESOURCE_INDEX_SQL} AS resources
        FROM webui_skill_snapshots AS snapshot
        LEFT JOIN webui_skill_snapshot_members AS membership
          ON membership.user_id = snapshot.user_id AND membership.conv_id = snapshot.conv_id
          AND membership.input_id = snapshot.input_id
        LEFT JOIN webui_skills AS skill
          ON skill.user_id = membership.user_id AND skill.skill_id = membership.skill_id
        LEFT JOIN webui_skill_members AS manifest
          ON manifest.user_id = membership.user_id AND manifest.skill_id = membership.skill_id
          AND manifest.path = 'SKILL.md'
        WHERE snapshot.user_id = ? AND snapshot.conv_id = ? AND snapshot.input_id = ?
        ORDER BY skill.name, membership.skill_id""",
        (user_id, conv_id, input_id),
    )
    if not rows:
        raise StateError("Admitted input skill snapshot is missing or inaccessible.")
    root_input_id = rows[0]["root_input_id"]
    revision = rows[0]["selection_revision"]
    if not isinstance(root_input_id, str) or not is_strict_int(revision):
        raise StateError("Admitted input skill snapshot has invalid identity.")
    available: list[AvailableSkill] = []
    explicit: list[tuple[int, str]] = []
    arguments: list[tuple[str, str]] = []
    for row in rows:
        skill_id = row["skill_id"]
        if skill_id is None:
            continue
        skill = available_skill_from_row(row)
        available.append(skill)
        ordinal = row["explicit_ordinal"]
        if ordinal is not None:
            if not is_strict_int(ordinal):
                raise StateError("Admitted skill invocation order is invalid.")
            explicit.append((ordinal, skill.skill_id))
            invocation_arguments = row["invocation_arguments"]
            if invocation_arguments is not None:
                if not isinstance(invocation_arguments, str):
                    raise StateError("Admitted skill arguments must be text.")
                arguments.append((skill.skill_id, invocation_arguments))
        elif row["invocation_arguments"] is not None:
            raise StateError("Skill arguments require an admitted human invocation.")
    explicit.sort()
    if [ordinal for ordinal, _skill_id in explicit] != list(range(len(explicit))):
        raise StateError("Admitted skill invocation order is inconsistent.")
    return SkillSnapshot(
        user_id,
        conv_id,
        input_id,
        root_input_id,
        revision,
        tuple(available),
        tuple(skill_id for _ordinal, skill_id in explicit),
        tuple(arguments),
    )


async def read_execution_skill_resource(
    connection: aiosqlite.Connection,
    identity: SkillExecutionIdentity,
    skill_id: str,
    path: str,
    supporting: bool = False,
) -> SkillMember:
    if identity.input_claim.input_id != identity.input_id:
        raise ValidationError("Skill resource claim belongs to another input.")
    row = await query_one_to_dict(
        connection,
        execution_skill_members_sql(supporting=supporting),
        (
            identity.user_id,
            identity.conv_id,
            identity.turn_id,
            identity.execution_token,
            get_boot_id(),
            identity.input_id,
            skill_id,
            path,
            path,
            identity.input_claim.input_id,
            identity.input_claim.generation,
            identity.input_claim.owner,
            identity.input_claim.server_boot_id,
        ),
    )
    if row is None:
        raise ValidationError("Skill resource is unavailable in this active execution.")
    return skill_member_from_row(row)
