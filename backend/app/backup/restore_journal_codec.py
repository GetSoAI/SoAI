"""SoAI - Restore journal V1 state codec [backend/app/backup/restore_journal_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.restore_destinations import ensure_restore_destination_is_safe
from core.backup.manifest import normalize_manifest_rel_path, validate_backup_id
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.identifiers import require_task_id
from core.types.json import JSONDict, JSONValue
from core.validation.epoch import require_unix_epoch_ms
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_int, require_non_empty_str

if TYPE_CHECKING:
    from typing import Literal

    type RestoreJournalPhase = Literal[
        "snapshotting",
        "prepared",
        "committing",
        "committed",
        "rolled_back",
    ]

_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class RestoreJournalItem:
    destination_path: str
    existed: bool


@dataclass(frozen=True, slots=True)
class RestoreCompletionRecord:
    task_id: str
    user_id: int
    backup_id: str
    cancellation_id: str
    database_path: str
    database_was_shutdown: bool
    completed_at_ms: int
    result: JSONDict


@dataclass(frozen=True, slots=True)
class RestoreJournalState:
    phase: RestoreJournalPhase
    snapshot_path: str
    items: dict[str, RestoreJournalItem]
    completion: RestoreCompletionRecord | None = None


def validate_restore_absolute_path(path: str, *, field: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValidationError(f"{field} is required.")
    normalized = os.path.abspath(path)
    if normalized != path:
        raise ValidationError(f"{field} must be a normalized absolute path.")
    ensure_restore_destination_is_safe(normalized)
    return normalized


def serialize_restore_journal_state(state: RestoreJournalState) -> str:
    items_payload: JSONDict = {}
    for relative_path, item in sorted(state.items.items()):
        items_payload[relative_path] = {
            "destination_path": item.destination_path,
            "existed": item.existed,
        }
    payload: JSONDict = {
        "schema_version": _SCHEMA_VERSION,
        "phase": state.phase,
        "snapshot_path": state.snapshot_path,
        "items": items_payload,
        "completion": _serialize_completion(state.completion),
    }
    return serialize_json_compact_stable_strict(payload, ensure_ascii=False)


def parse_restore_journal_state(raw: bytes, *, maximum_bytes: int) -> RestoreJournalState:
    if len(raw) > maximum_bytes:
        raise ValidationError("Restore journal exceeds the maximum size.")
    payload = parse_json_dict(raw, field="restore journal", reject_duplicate_keys=True)
    require_exact_json_fields(
        payload,
        allowed_fields={"schema_version", "phase", "snapshot_path", "items", "completion"},
        label="Restore journal",
    )
    schema_version = require_int(
        payload.get("schema_version"),
        label="Restore journal schema version",
        build_error=ValidationError,
    )
    if schema_version != _SCHEMA_VERSION:
        raise ValidationError("Restore journal schema version is invalid.")
    phase = _require_phase(payload.get("phase"))
    snapshot_path = validate_restore_absolute_path(
        _require_string(payload.get("snapshot_path"), "Restore journal snapshot_path"),
        field="Restore journal snapshot_path",
    )
    if os.path.basename(snapshot_path) != ".pre_restore_snapshot":
        raise ValidationError("Restore journal snapshot_path is invalid.")
    items = _parse_items(payload.get("items"))
    completion = _parse_completion(payload.get("completion"))
    if (phase == "committed") != (completion is not None):
        raise ValidationError("Restore journal completion does not match its phase.")
    return RestoreJournalState(phase, snapshot_path, items, completion)


def _parse_items(value: JSONValue) -> dict[str, RestoreJournalItem]:
    if not isinstance(value, dict) or not value:
        raise ValidationError("Restore journal items must be a non-empty object.")
    items: dict[str, RestoreJournalItem] = {}
    for raw_relative_path, raw_item in value.items():
        relative_path = normalize_manifest_rel_path(str(raw_relative_path))
        if relative_path != raw_relative_path or not isinstance(raw_item, dict):
            raise ValidationError("Restore journal item contract is invalid.")
        require_exact_json_fields(
            raw_item,
            allowed_fields={"destination_path", "existed"},
            label=f"Restore journal item {relative_path}",
        )
        destination_path = validate_restore_absolute_path(
            _require_string(
                raw_item.get("destination_path"),
                f"Restore destination for {relative_path}",
            ),
            field=f"Restore destination for {relative_path}",
        )
        existed = raw_item.get("existed")
        if not isinstance(existed, bool):
            raise ValidationError(f"Restore existed flag must be a bool for {relative_path}.")
        items[relative_path] = RestoreJournalItem(destination_path, existed)
    return items


def _parse_completion(value: JSONValue) -> RestoreCompletionRecord | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError("Restore journal completion must be an object.")
    require_exact_json_fields(
        value,
        allowed_fields={
            "task_id",
            "user_id",
            "backup_id",
            "cancellation_id",
            "database_path",
            "database_was_shutdown",
            "completed_at_ms",
            "result",
        },
        label="Restore journal completion",
    )
    task_id = require_task_id(
        value.get("task_id"),
        error_message="Restore task ID is invalid.",
    )
    user_id = require_int(
        value.get("user_id"), label="Restore user ID", build_error=ValidationError, minimum=1
    )
    raw_backup_id = _require_string(value.get("backup_id"), "Restore backup ID")
    backup_id = validate_backup_id(raw_backup_id)
    cancellation_id = require_cancellation_id(
        _require_string(value.get("cancellation_id"), "Restore cancellation ID")
    )
    database_path = validate_restore_absolute_path(
        _require_string(value.get("database_path"), "Restore database path"),
        field="Restore database path",
    )
    database_was_shutdown = value.get("database_was_shutdown")
    if not isinstance(database_was_shutdown, bool):
        raise ValidationError("Restore database shutdown state is invalid.")
    completed_at_ms = require_unix_epoch_ms(
        value.get("completed_at_ms"),
        error_message="Restore completion time is invalid.",
    )
    result = _parse_result(value.get("result"), backup_id)
    return RestoreCompletionRecord(
        task_id,
        user_id,
        backup_id,
        cancellation_id,
        database_path,
        database_was_shutdown,
        completed_at_ms,
        result,
    )


def _parse_result(value: JSONValue, backup_id: str) -> JSONDict:
    if not isinstance(value, dict):
        raise ValidationError("Restore completion result must be an object.")
    require_exact_json_fields(
        value,
        allowed_fields={"backup_id", "files_restored", "errors", "success", "rolled_back"},
        label="Restore completion result",
    )
    restored_files = value.get("files_restored")
    errors = value.get("errors")
    fixed_fields_valid = (
        value.get("backup_id"),
        errors,
        value.get("success"),
        value.get("rolled_back"),
    ) == (backup_id, [], True, False)
    if not isinstance(restored_files, list):
        raise ValidationError("Committed restore result is invalid.")
    if not fixed_fields_valid or any(
        not isinstance(item, str) or not item for item in restored_files
    ):
        raise ValidationError("Committed restore result is invalid.")
    return {
        "backup_id": backup_id,
        "files_restored": list(restored_files),
        "errors": [],
        "success": True,
        "rolled_back": False,
    }


def _serialize_completion(record: RestoreCompletionRecord | None) -> JSONValue:
    if record is None:
        return None
    return {
        "task_id": record.task_id,
        "user_id": record.user_id,
        "backup_id": record.backup_id,
        "cancellation_id": record.cancellation_id,
        "database_path": record.database_path,
        "database_was_shutdown": record.database_was_shutdown,
        "completed_at_ms": record.completed_at_ms,
        "result": record.result,
    }


def _require_phase(value: JSONValue) -> RestoreJournalPhase:
    if value == "snapshotting":
        return "snapshotting"
    if value == "prepared":
        return "prepared"
    if value == "committing":
        return "committing"
    if value == "committed":
        return "committed"
    if value == "rolled_back":
        return "rolled_back"
    raise ValidationError("Restore journal phase is invalid.")


def _require_string(value: JSONValue, field: str) -> str:
    return require_non_empty_str(value, label=field, build_error=ValidationError)


__all__ = (
    "RestoreCompletionRecord",
    "RestoreJournalItem",
    "RestoreJournalState",
    "parse_restore_journal_state",
    "serialize_restore_journal_state",
    "validate_restore_absolute_path",
)
