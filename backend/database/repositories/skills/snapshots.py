"""SoAI - Transactional skill availability capture at input admission [backend/database/repositories/skills/snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace

from core.conversations.settings_authority import resolve_conversation_settings_authority
from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.skills.compatibility_profiles import restore_skill_compatibility_profile
from core.skills.errors import build_skill_error
from core.skills.invocations import (
    resolve_skill_invocation_alias,
    resolve_skill_invocation_names,
    scan_skill_argument_bindings,
)
from core.types.json import JSONValue, is_str_list
from database.repositories.skills.selection import sync_get_skill_selection
from database.repositories.users.conversation_sync_operations import sync_get_conversation

__all__ = (
    "CapturedSkill",
    "CapturedSkills",
    "sync_prepare_skill_snapshot",
    "sync_store_skill_snapshot",
    "sync_capture_admitted_skills",
    "sync_prepare_regeneration_skills",
    "sync_transfer_forced_skills",
)


@dataclass(frozen=True, slots=True)
class CapturedSkill:
    skill_id: str
    package_digest: str
    name: str
    user_invocable: bool
    explicit_ordinal: int | None
    profile_digest: str
    invocation_arguments: str | None


@dataclass(frozen=True, slots=True)
class CapturedSkills:
    root_input_id: str | None
    selection_revision: int
    members: tuple[CapturedSkill, ...]


def sync_prepare_skill_snapshot(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    texts: tuple[str, ...],
    target_input_id: str | None = None,
) -> CapturedSkills:
    conversation = sync_get_conversation(connection, conv_id, user_id)
    if conversation is None:
        raise StateError("Skill admission lost its conversation owner.")
    if target_input_id is None:
        if resolve_conversation_settings_authority(conversation).is_read_only:
            return CapturedSkills(None, 0, ())
        selection = sync_get_skill_selection(connection, user_id, conv_id)
        revision = selection["revision"]
        if not isinstance(revision, int):
            raise StateError("Skill selection revision is invalid.")
        rows = connection.execute(
            """SELECT skill.skill_id, skill.package_digest, skill.name, skill.user_invocable, skill.profile_digest, skill.profile_json
            FROM webui_conversation_skills AS selection
            JOIN webui_skills AS skill ON skill.user_id = selection.user_id AND skill.skill_id = selection.skill_id
            WHERE selection.user_id = ? AND selection.conv_id = ? AND skill.removed_at_ms IS NULL
            ORDER BY skill.name, skill.skill_id""",
            (user_id, conv_id),
        ).fetchall()
        root_input_id = None
    else:
        header = connection.execute(
            """SELECT root_input_id, selection_revision FROM webui_skill_snapshots
            WHERE user_id = ? AND conv_id = ? AND input_id = ?""",
            (user_id, conv_id, target_input_id),
        ).fetchone()
        if header is None:
            raise StateError("Steering target has no captured skill state.")
        root_input_id, revision = str(header[0]), int(header[1])
        rows = connection.execute(
            """SELECT skill.skill_id, member.package_digest, skill.name, skill.user_invocable, member.profile_digest, skill.profile_json
            FROM webui_skill_snapshot_members AS member
            JOIN webui_skills AS skill ON skill.user_id = member.user_id AND skill.skill_id = member.skill_id
            WHERE member.user_id = ? AND member.conv_id = ? AND member.input_id = ?
            ORDER BY skill.name, skill.skill_id""",
            (user_id, conv_id, target_input_id),
        ).fetchall()
    available = {str(row[2]): bool(row[3]) for row in rows}
    aliases: dict[str, tuple[str, ...]] = {}
    for row in rows:
        profile = restore_skill_compatibility_profile(str(row[5]), str(row[4]))
        names = parse_json_dict(profile.content_json).get("aliases", [])
        if not is_str_list(names):
            raise StateError("Captured skill aliases are invalid.")
        for alias in names:
            aliases[alias] = (*aliases.get(alias, ()), str(row[2]))
    mentions = resolve_skill_invocation_names(texts, available, aliases)
    arguments: dict[str, str] = {}
    for text in texts:
        for invocation, bound_arguments in scan_skill_argument_bindings(text):
            name = resolve_skill_invocation_alias(invocation, available, aliases)
            if name in arguments and arguments[name] != bound_arguments:
                raise build_skill_error("skill_invocation_unavailable", reason="argument_conflict")
            arguments[name] = bound_arguments
    return CapturedSkills(
        root_input_id,
        revision,
        tuple(
            CapturedSkill(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                bool(row[3]),
                mentions.index(str(row[2])) if str(row[2]) in mentions else None,
                str(row[4]),
                arguments.get(str(row[2])),
            )
            for row in rows
        ),
    )


def sync_store_skill_snapshot(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    input_id: str,
    snapshot: CapturedSkills,
) -> None:
    connection.execute(
        """INSERT INTO webui_skill_snapshots
        (user_id, conv_id, input_id, root_input_id, selection_revision) VALUES (?, ?, ?, ?, ?)""",
        (
            user_id,
            conv_id,
            input_id,
            snapshot.root_input_id or input_id,
            snapshot.selection_revision,
        ),
    )
    connection.executemany(
        """INSERT INTO webui_skill_snapshot_members
        (user_id, conv_id, input_id, skill_id, package_digest, explicit_ordinal, profile_digest, invocation_arguments) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                user_id,
                conv_id,
                input_id,
                member.skill_id,
                member.package_digest,
                member.explicit_ordinal,
                member.profile_digest,
                member.invocation_arguments,
            )
            for member in snapshot.members
        ],
    )


def sync_capture_admitted_skills(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    input_id: str,
) -> None:
    row = connection.execute(
        """SELECT text, input_type, target_input_id, transport_origin FROM webui_conversation_inputs
        WHERE user_id = ? AND conv_id = ? AND input_id = ?""",
        (user_id, conv_id, input_id),
    ).fetchone()
    if row is None:
        raise StateError("Skill admission input disappeared.")
    snapshot = CapturedSkills(None, 0, ())
    if row[3] == "chat" and row[1] in {"prompt", "steer"}:
        snapshot = sync_prepare_skill_snapshot(
            connection,
            user_id,
            conv_id,
            (str(row[0]),),
            str(row[2]) if row[1] == "steer" and row[2] is not None else None,
        )
    sync_store_skill_snapshot(connection, user_id, conv_id, input_id, snapshot)


def sync_prepare_regeneration_skills(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    source_message_id: int,
) -> CapturedSkills:
    row = connection.execute(
        "SELECT content FROM webui_messages WHERE conv_id = ? AND id = ? AND role = 'user'",
        (conv_id, source_message_id),
    ).fetchone()
    if row is None:
        raise StateError("Skill regeneration source message disappeared.")
    content = parse_json_value(str(row[0]), field="regeneration source content")
    return sync_prepare_skill_snapshot(connection, user_id, conv_id, _human_text_parts(content))


def _human_text_parts(content: JSONValue) -> tuple[str, ...]:
    if isinstance(content, str):
        return (content,)
    if not isinstance(content, list):
        raise StateError("Skill regeneration source content is invalid.")
    texts: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if not isinstance(text, str):
                raise StateError("Skill regeneration source text is invalid.")
            texts.append(text)
    return tuple(texts)


def sync_transfer_forced_skills(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    input_id: str,
    executing_input_id: str,
    source_input_ids: list[str],
) -> None:
    baseline = sync_prepare_skill_snapshot(connection, user_id, conv_id, (), executing_input_id)
    explicit: list[str] = []
    arguments: dict[str, str] = {}
    for source_input_id in source_input_ids:
        state = connection.execute(
            """SELECT state FROM webui_conversation_inputs
            WHERE user_id = ? AND conv_id = ? AND input_id = ?""",
            (user_id, conv_id, source_input_id),
        ).fetchone()
        if state is None or state[0] != "pending":
            raise StateError("Forced skill source is no longer pending.")
        source = sync_prepare_skill_snapshot(connection, user_id, conv_id, (), source_input_id)
        if source != baseline:
            raise StateError("Forced steering cannot combine unrelated skill snapshots.")
        rows = connection.execute(
            """SELECT skill_id, invocation_arguments FROM webui_skill_snapshot_members
            WHERE user_id = ? AND conv_id = ? AND input_id = ? AND explicit_ordinal IS NOT NULL
            ORDER BY explicit_ordinal""",
            (user_id, conv_id, source_input_id),
        ).fetchall()
        for row in rows:
            skill_id = str(row[0])
            if skill_id not in explicit:
                explicit.append(skill_id)
            if row[1] is not None:
                value = str(row[1])
                if skill_id in arguments and arguments[skill_id] != value:
                    raise build_skill_error(
                        "skill_invocation_unavailable", reason="argument_conflict"
                    )
                arguments[skill_id] = value
    snapshot = CapturedSkills(
        baseline.root_input_id,
        baseline.selection_revision,
        tuple(
            replace(
                member,
                explicit_ordinal=(
                    explicit.index(member.skill_id) if member.skill_id in explicit else None
                ),
                invocation_arguments=arguments.get(member.skill_id),
            )
            for member in baseline.members
        ),
    )
    sync_store_skill_snapshot(connection, user_id, conv_id, input_id, snapshot)
