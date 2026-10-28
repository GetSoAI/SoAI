"""SoAI - Update snapshot diagnostic evidence, reports and typed preparation outcomes [backend/app/updater/software_update/install_transaction_snapshot_evidence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.updater.software_update.install_transaction_fingerprint import (
    FingerprintSnapshot,
    compare_fingerprint_descriptors,
    compute_fingerprint_aggregate,
)
from app.updater.software_update.install_transaction_inventory import RollbackContentMismatch
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.software_update_diagnostic_reports import (
    read_update_diagnostics_reference,
    write_update_diagnostics_report,
)
from core.tasks.software_update_diagnostics import (
    UpdateDiagnosticsContext,
    ensure_private_diagnostics_directory,
    require_private_diagnostics_directory,
)
from core.validation.strict_integer import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CHECK_INSTALLED_ORIGINAL",
    "CHECK_RECOPY",
    "CHECK_RETAINED_COPY",
    "CHECK_SNAPSHOT_COPY",
    "ExpectedDescriptors",
    "SnapshotProgress",
    "UpdateSnapshotEvidenceError",
    "UpdateSnapshotOutcomeError",
    "UpdateSnapshotPreparationError",
    "build_content_mismatch_report",
    "build_operation_failure_report",
    "discard_expected_descriptors",
    "read_expected_descriptors",
    "record_snapshot_report",
    "snapshot_preparation_failure",
    "write_expected_descriptors",
)

PREPARATION_PHASE = "snapshot_preparation"
EXPECTED_DESCRIPTORS_DIRECTORY = "expected"
EXPECTED_DESCRIPTORS_SCHEMA_VERSION = 1
MAX_EXPECTED_DESCRIPTORS_BYTES = 268435456
EXPECTED_DESCRIPTOR_FIELDS = frozenset(
    {"schema_version", "task_id", "transaction", "entry", "aggregate", "descriptors"}
)
CHECK_SNAPSHOT_COPY = "snapshot_copy"
CHECK_RETAINED_COPY = "retained_copy"
CHECK_INSTALLED_ORIGINAL = "installed_original"
CHECK_RECOPY = "recopy"


class UpdateSnapshotOutcomeError(StateError): ...


class UpdateSnapshotPreparationError(UpdateSnapshotOutcomeError): ...


class UpdateSnapshotEvidenceError(UpdateSnapshotOutcomeError): ...


@dataclass(frozen=True, slots=True)
class ExpectedDescriptors:
    status: str
    descriptors: dict[str, str] | None


@dataclass(slots=True)
class SnapshotProgress:
    check: str = CHECK_SNAPSHOT_COPY
    attempt: int = 1
    copy_seconds: float = 0.0
    sync_seconds: float = 0.0
    recopy_seconds: float = 0.0
    verification_seconds: float = 0.0

    def durations(self, traversal_seconds: float | None) -> JSONDict:
        return {
            "copy_seconds": self.copy_seconds,
            "sync_seconds": self.sync_seconds,
            "recopy_seconds": self.recopy_seconds,
            "verification_seconds": self.verification_seconds,
            "traversal_seconds": traversal_seconds,
        }


def build_content_mismatch_report(
    *,
    classification: str,
    mismatch: RollbackContentMismatch,
    expected: ExpectedDescriptors,
    progress: SnapshotProgress,
    recopy_forbidden_reason: str | None,
) -> JSONDict:
    comparison = (
        None
        if expected.descriptors is None
        else compare_fingerprint_descriptors(expected.descriptors, mismatch.actual.descriptors)
    )
    differences: list[JSONValue] = (
        []
        if comparison is None
        else [
            {
                "path": difference.path,
                "difference": difference.difference.value,
                "expected": difference.expected,
                "actual": difference.actual,
            }
            for difference in comparison.differences
        ]
    )
    return {
        "classification": classification,
        "phase": PREPARATION_PHASE,
        "check": progress.check,
        "entry": mismatch.entry,
        "entry_index": mismatch.entry_index,
        "attempt": progress.attempt,
        "expected_aggregate": mismatch.expected_aggregate,
        "actual_aggregate": mismatch.actual.aggregate,
        "expected_descriptors": expected.status,
        "expected_descriptor_count": (
            None if expected.descriptors is None else len(expected.descriptors)
        ),
        "actual_descriptor_count": len(mismatch.actual.descriptors),
        "total_differences": None if comparison is None else comparison.total_differences,
        "differences": differences,
        "differences_truncated": comparison is not None and comparison.is_truncated,
        "durations": progress.durations(mismatch.traversal_seconds),
        "error": None,
        "recopy_forbidden_reason": (
            recopy_forbidden_reason
            if recopy_forbidden_reason is not None or expected.descriptors is not None
            else "evidence_unavailable"
        ),
    }


def build_operation_failure_report(
    *,
    classification: str,
    progress: SnapshotProgress,
    entry: str | None,
    entry_index: int | None,
    exception: BaseException,
) -> JSONDict:
    return {
        "classification": classification,
        "phase": PREPARATION_PHASE,
        "check": progress.check,
        "entry": entry,
        "entry_index": entry_index,
        "attempt": progress.attempt,
        "durations": progress.durations(None),
        "error": {
            "category": type(exception).__name__,
            "os_error_code": exception.errno if isinstance(exception, OSError) else None,
        },
    }


def record_snapshot_report(
    context: UpdateDiagnosticsContext, report: JSONDict, *, cause: BaseException | None
) -> str:
    try:
        write_update_diagnostics_report(context, report)
        return read_update_diagnostics_reference(context)
    except (OSError, StateError, ValidationError) as storage_failure:
        raise UpdateSnapshotEvidenceError(
            "Update snapshot diagnostics could not be preserved; the transaction was retained.",
            details={"classification": "evidence_unavailable", "check": report["check"]},
            cause=cause if cause is not None else storage_failure,
        ) from storage_failure


def snapshot_preparation_failure(
    context: UpdateDiagnosticsContext, report: JSONDict, *, cause: BaseException | None
) -> UpdateSnapshotPreparationError:
    reference = record_snapshot_report(context, report, cause=cause)
    entry = report["entry"] or "the snapshot"
    return UpdateSnapshotPreparationError(
        f"Update snapshot {report['check']} failed for {entry}; diagnostic reference {reference}.",
        details={
            "classification": report["classification"],
            "check": report["check"],
            "entry": report["entry"],
            "attempt": report["attempt"],
            "reference": reference,
            "location": context.location,
        },
        cause=cause,
    )


def _expected_descriptors_path(context: UpdateDiagnosticsContext, index: int) -> str:
    return os.path.join(context.location, EXPECTED_DESCRIPTORS_DIRECTORY, f"{index:04d}.json")


def write_expected_descriptors(
    context: UpdateDiagnosticsContext, *, index: int, entry: str, snapshot: FingerprintSnapshot
) -> None:
    require_private_diagnostics_directory(context.location)
    ensure_private_diagnostics_directory(
        os.path.join(context.location, EXPECTED_DESCRIPTORS_DIRECTORY)
    )
    atomic_create_text_content_exclusive(
        _expected_descriptors_path(context, index),
        serialize_json_compact_stable_strict(
            {
                "schema_version": EXPECTED_DESCRIPTORS_SCHEMA_VERSION,
                "task_id": context.task_id,
                "transaction": context.transaction,
                "entry": entry,
                "aggregate": snapshot.aggregate,
                "descriptors": snapshot.descriptors,
            }
        ),
        ensure_parent=False,
        file_mode=0o600,
        fsync_parent_directory=True,
    )


def read_expected_descriptors(
    context: UpdateDiagnosticsContext, *, index: int, entry: str, aggregate: str
) -> ExpectedDescriptors:
    path = _expected_descriptors_path(context, index)
    if not os.path.lexists(path):
        return ExpectedDescriptors("missing", None)
    try:
        require_private_diagnostics_directory(os.path.dirname(path))
        payload = parse_json_dict(
            read_regular_file_no_symlink(path, max_bytes=MAX_EXPECTED_DESCRIPTORS_BYTES),
            field="update expected descriptors",
            reject_duplicate_keys=True,
        )
        descriptors = payload.get("descriptors")
        binding = {
            "schema_version": EXPECTED_DESCRIPTORS_SCHEMA_VERSION,
            "task_id": context.task_id,
            "transaction": context.transaction,
            "entry": entry,
            "aggregate": aggregate,
        }
        if (
            frozenset(payload) != EXPECTED_DESCRIPTOR_FIELDS
            or not is_strict_int(payload.get("schema_version"))
            or any(payload.get(name) != value for name, value in binding.items())
            or not isinstance(descriptors, dict)
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in descriptors.items()
            )
        ):
            return ExpectedDescriptors("invalid", None)
        verified = {str(key): str(value) for key, value in descriptors.items()}
    except (OSError, StateError, ValidationError):
        return ExpectedDescriptors("invalid", None)
    if compute_fingerprint_aggregate(verified) != aggregate:
        return ExpectedDescriptors("invalid", None)
    return ExpectedDescriptors("available", verified)


def discard_expected_descriptors(context: UpdateDiagnosticsContext) -> None:
    require_private_diagnostics_directory(context.location)
    expected_path = os.path.join(context.location, EXPECTED_DESCRIPTORS_DIRECTORY)
    if os.path.lexists(expected_path):
        require_private_diagnostics_directory(expected_path)
    sync_remove_tree_no_symlinks(expected_path)
