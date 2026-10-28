"""SoAI - Atomic materialization receipts, admission and publication evidence [backend/database/repositories/skills/materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import MutationAdmissionRequest
from core.errors.exceptions import StateError, ValidationError
from core.runtime.boot_id import get_boot_id
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.skills.materialization import (
    SkillMaterializationReceipt,
    SkillMaterializationRequest,
    restore_directory_identity,
)
from core.skills.records import SkillMember
from core.skills.serialization import restore_skill_resources, skill_resources_payload
from core.types.json import JSONValue
from database.repositories.skills.content import skill_member_from_row
from database.repositories.skills.execution_reads import execution_skill_members_sql
from database.repositories.skills.materialization_sources import (
    sync_project_materialization_sources,
)
from database.repositories.tasks.mutation_lifecycle import sync_advance_mutation_execution

__all__ = (
    "sync_find_materialization",
    "sync_materialization_members",
    "sync_read_materialization",
    "sync_materialization_replay",
    "sync_insert_materialization",
    "sync_checkpoint_materialization",
)


def sync_find_materialization(
    connection: sqlite3.Connection, user_id: int, operation_key: str
) -> SkillMaterializationReceipt | None:
    row = connection.execute(
        "SELECT request_id FROM webui_skill_materializations WHERE user_id=? AND operation_key=?",
        (user_id, operation_key),
    ).fetchone()
    return (
        None if row is None else sync_read_materialization(connection, row["request_id"], user_id)
    )


def sync_materialization_members(
    connection: sqlite3.Connection, request: SkillMaterializationRequest
) -> tuple[SkillMember, ...]:
    members = tuple(
        skill_member_from_row(dict(row))
        for row in _materialization_cursor(connection, request, None).fetchall()
    )
    if not members:
        return ()
    return sync_project_materialization_sources(connection, request, members)


def _materialization_cursor(
    connection: sqlite3.Connection, request: SkillMaterializationRequest, path: str | None
) -> sqlite3.Cursor:
    identity = request.identity
    cursor = connection.execute(
        f"""{execution_skill_members_sql()} AND EXISTS
        (SELECT 1 FROM webui_skill_snapshots AS root WHERE root.user_id=snapshot.user_id
        AND root.conv_id=snapshot.conv_id AND root.input_id=snapshot.input_id AND root.root_input_id=?)
        AND snapshot.package_digest=? ORDER BY member.path""",
        (
            identity.user_id,
            identity.conv_id,
            identity.turn_id,
            identity.execution_token,
            get_boot_id(),
            identity.input_id,
            request.skill_id,
            path,
            path,
            identity.input_claim.input_id,
            identity.input_claim.generation,
            identity.input_claim.owner,
            identity.input_claim.server_boot_id,
            request.root_input_id,
            request.package_digest,
        ),
    )
    return cursor


def sync_read_materialization(
    connection: sqlite3.Connection, request_id: str, user_id: int
) -> SkillMaterializationReceipt | None:
    row = connection.execute(
        """SELECT receipt.*, admission.execution_phase, admission.execution_state, admission.lifecycle_status FROM webui_skill_materializations AS receipt
        LEFT JOIN mutation_admissions AS admission ON admission.request_id=receipt.request_id
        WHERE receipt.request_id=? AND receipt.user_id=?""",
        (request_id, user_id),
    ).fetchone()
    if row is None:
        return None
    request = SkillMaterializationRequest.restore(
        parse_json_dict(row["request_json"], field="Skill materialization request")
    )
    if (
        request.identity.user_id != user_id
        or request.skill_id != row["skill_id"]
        or request.operation_key != row["operation_key"]
    ):
        raise StateError("Skill materialization receipt identity is inconsistent.")
    failure_cancelled = False
    cleanup_required: str | None = None
    if row["execution_phase"] == "contained_failure":
        state = parse_json_dict(row["execution_state"], field="Skill failure evidence")
        if set(state) != {"cancelled", "staging_cleanup_required"} or not isinstance(
            state["cancelled"], bool
        ):
            raise StateError("Skill failure evidence is inconsistent.")
        cleanup = state["staging_cleanup_required"]
        if cleanup is not None:
            if not isinstance(cleanup, str) or cleanup != f".soai-skill-{request_id}":
                raise StateError("Skill failure cleanup evidence is inconsistent.")
            cleanup_required = cleanup
        failure_cancelled = state["cancelled"]
    staging = row["staging_identity_json"]
    publication = row["publication_identity_json"]
    return SkillMaterializationReceipt(
        request_id,
        request,
        restore_skill_resources(
            parse_json_value(row["resources_json"], field="Skill materialization resources"),
            manifest_path=request.manifest_path,
        ),
        (
            None
            if staging is None
            else restore_directory_identity(
                parse_json_value(staging, field="Skill staging identity")
            )
        ),
        (
            None
            if publication is None
            else restore_directory_identity(
                parse_json_value(publication, field="Skill publication identity")
            )
        ),
        row["terminal_status"],
        (
            None
            if row["terminal_result"] is None
            else parse_json_dict(row["terminal_result"], field="Skill materialization result")
        ),
        row["execution_phase"],
        failure_cancelled,
        cleanup_required,
        row["lifecycle_status"] == "recovery_required",
    )


def sync_materialization_replay(
    connection: sqlite3.Connection, admission: MutationAdmissionRequest
) -> str | None:
    request = SkillMaterializationRequest.restore(
        parse_json_dict(admission.command_payload, field="Skill materialization request")
    )
    if admission.schema_discriminator != "skill_materialize_v1":
        raise ValidationError("Skill materialization admission discriminator is inconsistent.")
    if (
        admission.authorization_scope != "mcp_use"
        or admission.owner_id != str(request.identity.user_id)
        or admission.target_identity != request.operation_key
        or admission.conflict_keys != (f"skill_materialize:{request.operation_key}",)
        or admission.shared_conflict_keys
    ):
        raise ValidationError("Skill materialization admission authority is inconsistent.")
    reused = connection.execute(
        "SELECT operation_key FROM webui_skill_materializations WHERE request_id=?",
        (admission.request_id,),
    ).fetchone()
    if reused is not None and reused["operation_key"] != request.operation_key:
        raise StateError("Materialization request identity was reused for another operation.")
    row = connection.execute(
        "SELECT request_id FROM webui_skill_materializations WHERE operation_key=?",
        (request.operation_key,),
    ).fetchone()
    return None if row is None else str(row["request_id"])


def sync_insert_materialization(
    connection: sqlite3.Connection, admission: MutationAdmissionRequest
) -> None:
    request = SkillMaterializationRequest.restore(
        parse_json_dict(admission.command_payload, field="Skill materialization request")
    )
    members = sync_materialization_members(connection, request)
    if not members:
        raise ValidationError(
            "Skill materialization requires committed activation and a live execution."
        )
    connection.execute(
        """INSERT INTO webui_skill_materializations
        (request_id, operation_key, user_id, skill_id, request_json, resources_json)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            admission.request_id,
            request.operation_key,
            request.identity.user_id,
            request.skill_id,
            admission.command_payload,
            serialize_json_compact_stable(
                skill_resources_payload(tuple(member.resource for member in members))
            ),
        ),
    )


def sync_checkpoint_materialization(
    connection: sqlite3.Connection,
    request_id: str,
    user_id: int,
    fencing_token: int,
    expected_phase: str,
    next_phase: str,
    directory_identity: tuple[int, int] | None,
    now_ms: int,
    cancelled: bool = False,
) -> None:
    receipt = sync_read_materialization(connection, request_id, user_id)
    if receipt is None or receipt.terminal_status is not None:
        raise StateError("Materialization receipt is unavailable for checkpointing.")
    transitions = {
        ("accepted", "creating"),
        ("creating", "staging"),
        ("staging", "publishing"),
        ("publishing", "verified"),
        ("accepted", "contained_failure"),
        ("creating", "contained_failure"),
        ("staging", "contained_failure"),
        ("publishing", "contained_failure"),
        ("publishing", "conflict"),
        ("verified", "conflict"),
    }
    if (expected_phase, next_phase) not in transitions:
        raise StateError("Materialization checkpoint transition is invalid.")
    identity_payload: JSONValue = (
        None if directory_identity is None else [str(part) for part in directory_identity]
    )
    identity_json = (
        None if identity_payload is None else serialize_json_compact_stable(identity_payload)
    )
    if next_phase in {"staging", "publishing", "verified"} and directory_identity is None:
        raise StateError("Materialization checkpoint requires directory identity evidence.")
    if next_phase == "publishing" and receipt.staging_identity != directory_identity:
        raise StateError("Materialization publication differs from the owned staging directory.")
    if next_phase == "publishing":
        if _materialization_cursor(connection, receipt.request, "SKILL.md").fetchone() is None:
            raise ValidationError("Materialization execution ended before publication admission.")
        task = connection.execute(
            "SELECT cancellation_requested_at_ms FROM unified_tasks WHERE task_id=?", (request_id,)
        ).fetchone()
        if task is None or task["cancellation_requested_at_ms"] is not None:
            raise ValidationError("Materialization was cancelled before publication admission.")
    if next_phase == "verified" and receipt.publication_identity != directory_identity:
        raise StateError("Materialization completion differs from its publication evidence.")
    state: JSONValue = {}
    if next_phase == "contained_failure":
        state = {
            "cancelled": cancelled,
            "staging_cleanup_required": (
                receipt.staging_name
                if expected_phase == "creating" and receipt.staging_identity is None
                else None
            ),
        }
    if not sync_advance_mutation_execution(
        connection,
        request_id,
        fencing_token,
        expected_phase,
        next_phase,
        serialize_json_compact_stable(state),
        now_ms,
    ):
        raise StateError("Materialization mutation claim is no longer current.")
    if next_phase == "staging":
        connection.execute(
            "UPDATE webui_skill_materializations SET staging_identity_json=? WHERE request_id=?",
            (identity_json, request_id),
        )
    elif next_phase == "publishing":
        connection.execute(
            "UPDATE webui_skill_materializations SET publication_identity_json=? WHERE request_id=?",
            (identity_json, request_id),
        )
