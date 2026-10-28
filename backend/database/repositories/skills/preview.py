"""SoAI - Read-only coherent skill prompt previews [backend/database/repositories/skills/preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.skills.execution import SkillSnapshot
from database.core.query_execution import sync_fetch_all_as_dicts
from database.repositories.skills.content import SKILL_RESOURCE_INDEX_SQL, available_skill_from_row
from database.repositories.skills.snapshots import sync_prepare_skill_snapshot
from database.repositories.users.conversation_input_constants import TERMINAL_INPUT_STATES

__all__ = ("sync_skill_read_preview",)


def sync_skill_read_preview(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    text: str,
    target_input_id: str | None,
) -> SkillSnapshot:
    if target_input_id is not None:
        target = connection.execute(
            "SELECT state FROM webui_conversation_inputs WHERE user_id = ? AND conv_id = ? AND input_id = ?",
            (user_id, conv_id, target_input_id),
        ).fetchone()
        if target is None or target[0] in TERMINAL_INPUT_STATES:
            raise ValidationError("Skill preview requires a current steering target.")
    captured = sync_prepare_skill_snapshot(connection, user_id, conv_id, (text,), target_input_id)
    identities = [member.skill_id for member in captured.members]
    rows = sync_fetch_all_as_dicts(
        connection.execute(
            f"""SELECT skill.skill_id, skill.package_digest, skill.package_digest AS retained_digest,
            skill.profile_digest, skill.profile_digest AS retained_profile_digest, skill.profile_json,
            skill.name, skill.disable_model_invocation, skill.user_invocable, skill.manifest_json,
            manifest.path, manifest.is_directory, manifest.content, manifest.digest,
            {SKILL_RESOURCE_INDEX_SQL} AS resources
        FROM webui_skills AS skill
        JOIN webui_skill_members AS manifest
          ON manifest.user_id = skill.user_id AND manifest.skill_id = skill.skill_id
          AND manifest.path = 'SKILL.md'
        WHERE skill.user_id = ? AND skill.skill_id IN (SELECT value FROM json_each(?))
        ORDER BY skill.name, skill.skill_id""",
            (user_id, serialize_json_compact_stable_strict(identities)),
        )
    )
    available = tuple(available_skill_from_row(row) for row in rows)
    if {(item.skill_id, item.package_digest) for item in available} != {
        (item.skill_id, item.package_digest) for item in captured.members
    }:
        raise StateError("Skill preview content differs from its selection.")
    explicit = sorted(
        (member.explicit_ordinal, member.skill_id)
        for member in captured.members
        if member.explicit_ordinal is not None
    )
    return SkillSnapshot(
        user_id,
        conv_id,
        target_input_id or "",
        captured.root_input_id or "",
        captured.selection_revision,
        available,
        tuple(skill_id for _ordinal, skill_id in explicit),
        tuple(
            (member.skill_id, member.invocation_arguments)
            for member in captured.members
            if member.invocation_arguments is not None
        ),
    )
