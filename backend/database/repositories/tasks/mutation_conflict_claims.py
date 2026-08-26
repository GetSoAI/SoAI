"""SoAI - Durable shared and exclusive mutation conflict claims [backend/database/repositories/tasks/mutation_conflict_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import MutationAdmissionRequest
from core.errors.exceptions import ValidationError
from core.plugins.mutation_conflicts import (
    build_plugin_lifecycle_conflict_key,
    extract_plugin_lifecycle_conflict_target,
)
from core.serialization.json import serialize_json_compact_stable

__all__ = (
    "find_mutation_conflict_owner",
    "insert_mutation_conflict_claims",
    "insert_reserved_target_conflict_claim",
    "serialize_mutation_conflict_keys",
    "validate_mutation_conflict_keys",
)


def validate_mutation_conflict_keys(request: MutationAdmissionRequest) -> None:
    all_keys = request.conflict_keys + request.shared_conflict_keys
    if not all_keys:
        raise ValidationError("Mutation admission requires conflict claims.")
    if any(not key for key in all_keys):
        raise ValidationError("Mutation admission conflict keys must be non-empty.")
    if len(set(all_keys)) != len(all_keys):
        raise ValidationError("Mutation conflict keys must be unique across access modes.")
    if request.conflict_keys != tuple(sorted(request.conflict_keys)):
        raise ValidationError("Exclusive mutation conflict keys must use canonical sorted order.")
    if request.shared_conflict_keys != tuple(sorted(request.shared_conflict_keys)):
        raise ValidationError("Shared mutation conflict keys must use canonical sorted order.")


def serialize_mutation_conflict_keys(conflict_keys: tuple[str, ...]) -> str:
    return serialize_json_compact_stable(list(conflict_keys))


def _find_claim_owner(
    connection: sqlite3.Connection,
    request: MutationAdmissionRequest,
) -> tuple[str, str] | None:
    conditions: list[str] = []
    parameters: list[str] = []
    if request.conflict_keys:
        placeholders = ",".join("?" for _ in request.conflict_keys)
        conditions.append(f"claim.conflict_key IN ({placeholders})")
        parameters.extend(request.conflict_keys)
    if request.shared_conflict_keys:
        placeholders = ",".join("?" for _ in request.shared_conflict_keys)
        conditions.append(
            f"(claim.access_mode = 'exclusive' AND claim.conflict_key IN ({placeholders}))"
        )
        parameters.extend(request.shared_conflict_keys)
    conflict = connection.execute(
        f"""SELECT admission.accepted_task_id, admission.owner_id
        FROM mutation_conflict_keys AS claim
        JOIN mutation_admissions AS admission ON admission.request_id = claim.request_id
        WHERE {' OR '.join(conditions)}
        ORDER BY admission.accepted_at_ms, claim.conflict_key, admission.request_id LIMIT 1""",
        parameters,
    ).fetchone()
    if conflict is None:
        return None
    return (conflict["accepted_task_id"], conflict["owner_id"])


def _find_reservation_owner(
    connection: sqlite3.Connection,
    conflict_keys: tuple[str, ...],
) -> tuple[str, str] | None:
    reservation_targets = tuple(
        target
        for key in conflict_keys
        if (target := extract_plugin_lifecycle_conflict_target(key)) is not None
    )
    if not reservation_targets:
        return None
    placeholders = ",".join("?" for _ in reservation_targets)
    reservation = connection.execute(
        f"""SELECT reservation.task_id, admission.owner_id
        FROM plugin_clone_target_reservations AS reservation
        LEFT JOIN mutation_admissions AS admission
            ON admission.accepted_task_id = reservation.task_id
        WHERE reservation.target_plugin_name IN ({placeholders})
        ORDER BY reservation.target_plugin_name LIMIT 1""",
        reservation_targets,
    ).fetchone()
    if reservation is None:
        return None
    return (reservation["task_id"], reservation["owner_id"] or "")


def find_mutation_conflict_owner(
    connection: sqlite3.Connection,
    request: MutationAdmissionRequest,
) -> tuple[str, str] | None:
    claim_owner = _find_claim_owner(connection, request)
    if claim_owner is not None:
        return claim_owner
    return _find_reservation_owner(connection, request.conflict_keys)


def insert_mutation_conflict_claims(
    connection: sqlite3.Connection,
    request: MutationAdmissionRequest,
) -> None:
    connection.executemany(
        """INSERT INTO mutation_conflict_keys (
            conflict_key, request_id, access_mode, reservation_target_name
        ) VALUES (?, ?, ?, NULL)""",
        (
            *((key, request.request_id, "exclusive") for key in request.conflict_keys),
            *((key, request.request_id, "shared") for key in request.shared_conflict_keys),
        ),
    )


def insert_reserved_target_conflict_claim(
    connection: sqlite3.Connection,
    request_id: str,
    target_plugin_name: str,
) -> None:
    connection.execute(
        """INSERT INTO mutation_conflict_keys (
            conflict_key, request_id, access_mode, reservation_target_name
        ) VALUES (?, ?, 'exclusive', ?)""",
        (
            build_plugin_lifecycle_conflict_key(target_plugin_name),
            request_id,
            target_plugin_name,
        ),
    )
