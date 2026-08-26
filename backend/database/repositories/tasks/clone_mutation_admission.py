"""SoAI - Atomic clone target allocation during mutation admission [backend/database/repositories/tasks/clone_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import MutationAdmissionRequest
from core.errors.exceptions import StateError
from core.plugins.clone_target_candidates import iter_clone_target_candidates
from core.plugins.mutation_conflicts import build_plugin_lifecycle_conflict_key
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.json_parsing import parse_json_dict

__all__ = (
    "reserve_clone_target_for_admission",
    "validate_clone_admission_request",
)


def validate_clone_admission_request(
    request: MutationAdmissionRequest,
) -> tuple[str, str | None, bool]:
    payload = parse_json_dict(request.command_payload, field="command_payload")
    if frozenset(payload) != frozenset(
        (
            "clone_models",
            "field_override_names",
            "field_overrides_fingerprint",
            "plugin_name",
            "target_name",
        )
    ):
        raise StateError("Clone mutation admission payload does not match its V1 schema.")
    source_value = payload["plugin_name"]
    target_value = payload["target_name"]
    clone_models = payload["clone_models"]
    override_names = payload["field_override_names"]
    override_fingerprint = payload["field_overrides_fingerprint"]
    if not isinstance(source_value, str):
        raise StateError("Clone mutation admission source identity is invalid.")
    source_name = require_portable_plugin_identifier(
        source_value,
        field_name="plugin_name",
    )
    if target_value is not None and not isinstance(target_value, str):
        raise StateError("Clone mutation admission target identity is invalid.")
    target_name = (
        require_portable_plugin_identifier(target_value, field_name="target_name")
        if target_value is not None
        else None
    )
    if not isinstance(clone_models, bool):
        raise StateError("Clone mutation admission clone_models value is invalid.")
    if not isinstance(override_names, list):
        raise StateError("Clone mutation admission override names are invalid.")
    decoded_override_names: list[str] = []
    for override_name in override_names:
        if not isinstance(override_name, str) or not override_name:
            raise StateError("Clone mutation admission override names are invalid.")
        decoded_override_names.append(override_name)
    if decoded_override_names != sorted(set(decoded_override_names)):
        raise StateError("Clone mutation admission override names are invalid.")
    has_recovery_payload = request.recovery_payload_encrypted is not None
    valid_fingerprint = (
        isinstance(override_fingerprint, str)
        and len(override_fingerprint) == 64
        and all(character in "0123456789abcdef" for character in override_fingerprint)
    )
    if has_recovery_payload != valid_fingerprint:
        raise StateError("Clone mutation admission recovery contract is invalid.")
    return (source_name, target_name, clone_models)


def _candidate_is_occupied(connection: sqlite3.Connection, candidate: str) -> bool:
    catalog = connection.execute(
        "SELECT 1 FROM plugins_catalog WHERE plugin_name = ?",
        (candidate,),
    ).fetchone()
    if catalog is not None:
        return True
    reservation = connection.execute(
        "SELECT 1 FROM plugin_clone_target_reservations WHERE target_plugin_name = ?",
        (candidate,),
    ).fetchone()
    if reservation is not None:
        return True
    conflict = connection.execute(
        "SELECT 1 FROM mutation_conflict_keys WHERE conflict_key = ?",
        (build_plugin_lifecycle_conflict_key(candidate),),
    ).fetchone()
    return conflict is not None


def _select_target(
    connection: sqlite3.Connection,
    source_name: str,
    requested_target_name: str | None,
    excluded_target_names: frozenset[str],
) -> str | None:
    if requested_target_name is not None:
        return (
            None
            if requested_target_name in excluded_target_names
            or _candidate_is_occupied(connection, requested_target_name)
            else requested_target_name
        )
    for candidate in iter_clone_target_candidates(source_name):
        if candidate not in excluded_target_names and not _candidate_is_occupied(
            connection,
            candidate,
        ):
            return candidate
    return None


def reserve_clone_target_for_admission(
    connection: sqlite3.Connection,
    request: MutationAdmissionRequest,
    *,
    created_at_ms: int,
) -> str | None:
    source_name, requested_target_name, clone_models = validate_clone_admission_request(request)
    excluded_target_names = frozenset(
        require_portable_plugin_identifier(name, field_name="excluded_target_name")
        for name in request.excluded_target_names
    )
    target_name = _select_target(
        connection,
        source_name,
        requested_target_name,
        excluded_target_names,
    )
    if target_name is None:
        return None
    connection.execute(
        """INSERT INTO plugin_clone_transactions (
            task_id, source_plugin_name, requested_target_name, target_plugin_name,
            clone_models, created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        (
            request.accepted_task_id,
            source_name,
            requested_target_name,
            target_name,
            int(clone_models),
            created_at_ms,
        ),
    )
    connection.execute(
        """INSERT INTO plugin_clone_target_reservations (target_plugin_name, task_id)
        VALUES (?, ?)""",
        (target_name, request.accepted_task_id),
    )
    return target_name
