"""SoAI - Immutable software update diagnostic reports and preservation receipts [backend/core/tasks/software_update_diagnostic_reports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.software_update_diagnostics import (
    MAX_DIAGNOSTICS_RECORD_BYTES,
    UpdateDiagnosticsContext,
    read_update_diagnostics_locator,
    require_private_diagnostics_directory,
    update_diagnostics_locator_path,
)
from core.validation.strict_integer import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DIAGNOSTIC_CLASSIFICATIONS",
    "UpdateDiagnosticsSummary",
    "preserve_update_diagnostics",
    "read_update_diagnostics_reference",
    "not_recorded_update_diagnostics",
    "read_update_diagnostics_summary",
    "record_interrupted_update_preparation",
    "release_update_diagnostics",
    "unavailable_update_diagnostics",
    "verify_update_diagnostics_preserved",
    "write_update_diagnostics_report",
)

SCHEMA_VERSION = 1
RECEIPT_FILENAME = "receipt.json"
REPORT_FILENAME_PREFIX = "report-"
REPORT_FILENAME_SUFFIX = ".json"
REPORT_NUMBER_DIGITS = 4
REFERENCE_HEX_LENGTH = 16
DIAGNOSTIC_CLASSIFICATIONS = frozenset(
    {
        "retained_copy_mismatch",
        "installed_original_changed",
        "source_unverifiable",
        "snapshot_operation_failed",
        "interrupted_preparation",
    }
)
RECEIPT_FIELDS = frozenset(
    {"schema_version", "task_id", "transaction", "installation", "reports", "report_digest"}
)


@dataclass(frozen=True, slots=True)
class UpdateDiagnosticsSummary:
    status: str
    location: str | None
    classification: str | None
    reference: str | None

    def to_public_payload(self, task_id: str) -> JSONDict:
        return {
            "task_id": task_id,
            "status": self.status,
            "location": self.location,
            "classification": self.classification,
            "reference": self.reference,
        }


def not_recorded_update_diagnostics() -> UpdateDiagnosticsSummary:
    return UpdateDiagnosticsSummary("not_recorded", None, None, None)


def unavailable_update_diagnostics() -> UpdateDiagnosticsSummary:
    return UpdateDiagnosticsSummary("unavailable", None, None, None)


def _is_report_name(name: str) -> bool:
    number = name.removeprefix(REPORT_FILENAME_PREFIX).removesuffix(REPORT_FILENAME_SUFFIX)
    return (
        name.startswith(REPORT_FILENAME_PREFIX)
        and name.endswith(REPORT_FILENAME_SUFFIX)
        and len(number) == REPORT_NUMBER_DIGITS
        and number.isascii()
        and number.isdigit()
    )


def _report_names(location: str) -> tuple[str, ...]:
    require_private_diagnostics_directory(location)
    names = tuple(sorted(name for name in os.listdir(location) if _is_report_name(name)))
    for name in names:
        path = os.path.join(location, name)
        if os.path.islink(path) or not os.path.isfile(path):
            raise StateError("Update diagnostics report is not a regular file.")
    return names


def _read_report(context: UpdateDiagnosticsContext, name: str) -> JSONDict:
    payload = parse_json_dict(
        read_regular_file_no_symlink(
            os.path.join(context.location, name), max_bytes=MAX_DIAGNOSTICS_RECORD_BYTES
        ),
        field="update diagnostics report",
        reject_duplicate_keys=True,
    )
    binding = {
        "schema_version": SCHEMA_VERSION,
        "task_id": context.task_id,
        "transaction": context.transaction,
        "from_version": context.from_version,
        "to_version": context.to_version,
        "location": context.location,
    }
    classification = payload.get("classification")
    if (
        not is_strict_int(payload.get("schema_version"))
        or any(payload.get(name) != value for name, value in binding.items())
        or not isinstance(classification, str)
        or classification not in DIAGNOSTIC_CLASSIFICATIONS
    ):
        raise StateError("Update diagnostics report does not match its operation.")
    return payload


def _reports_digest(location: str, names: tuple[str, ...]) -> str:
    entries: list[JSONValue] = [
        {
            "name": name,
            "sha256": hashlib.sha256(
                read_regular_file_no_symlink(
                    os.path.join(location, name), max_bytes=MAX_DIAGNOSTICS_RECORD_BYTES
                )
            ).hexdigest(),
        }
        for name in names
    ]
    return hashlib.sha256(serialize_json_compact_stable_strict(entries).encode("utf-8")).hexdigest()


def write_update_diagnostics_report(context: UpdateDiagnosticsContext, report: JSONDict) -> str:
    classification = report.get("classification")
    if not isinstance(classification, str) or classification not in DIAGNOSTIC_CLASSIFICATIONS:
        raise StateError("Update diagnostics report classification is invalid.")
    name = f"report-{len(_report_names(context.location)) + 1:04d}.json"
    atomic_create_text_content_exclusive(
        os.path.join(context.location, name),
        serialize_json_compact_stable_strict(
            {
                **report,
                "schema_version": SCHEMA_VERSION,
                "task_id": context.task_id,
                "transaction": context.transaction,
                "from_version": context.from_version,
                "to_version": context.to_version,
                "location": context.location,
            }
        ),
        ensure_parent=False,
        file_mode=0o600,
        fsync_parent_directory=True,
    )
    return name


def _receipt_payload(context: UpdateDiagnosticsContext, names: tuple[str, ...]) -> JSONDict:
    for name in names:
        _read_report(context, name)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": context.task_id,
        "transaction": context.transaction,
        "installation": context.installation,
        "reports": list(names),
        "report_digest": _reports_digest(context.location, names),
    }


def _read_receipt(context: UpdateDiagnosticsContext) -> JSONDict:
    receipt = parse_json_dict(
        read_regular_file_no_symlink(
            os.path.join(context.location, RECEIPT_FILENAME),
            max_bytes=MAX_DIAGNOSTICS_RECORD_BYTES,
        ),
        field="update diagnostics receipt",
        reject_duplicate_keys=True,
    )
    if frozenset(receipt) != RECEIPT_FIELDS or not is_strict_int(receipt.get("schema_version")):
        raise StateError("Update diagnostics receipt does not match its contract.")
    return receipt


def preserve_update_diagnostics(context: UpdateDiagnosticsContext) -> bool:
    require_private_diagnostics_directory(context.location)
    names = _report_names(context.location)
    payload = _receipt_payload(context, names)
    try:
        atomic_create_text_content_exclusive(
            os.path.join(context.location, RECEIPT_FILENAME),
            serialize_json_compact_stable_strict(payload),
            ensure_parent=False,
            file_mode=0o600,
            fsync_parent_directory=True,
        )
    except FileExistsError as exception:
        if _read_receipt(context) != payload:
            raise StateError(
                "Preserved update diagnostics changed after their receipt."
            ) from exception
    return bool(names)


def verify_update_diagnostics_preserved(context: UpdateDiagnosticsContext) -> None:
    require_private_diagnostics_directory(context.location)
    names = _report_names(context.location)
    receipt_exists = os.path.lexists(os.path.join(context.location, RECEIPT_FILENAME))
    if not receipt_exists or _read_receipt(context) != _receipt_payload(context, names):
        raise StateError("Update diagnostics are not preserved by a valid receipt.")


def read_update_diagnostics_reference(context: UpdateDiagnosticsContext) -> str:
    return _reports_digest(context.location, _report_names(context.location))[:REFERENCE_HEX_LENGTH]


def record_interrupted_update_preparation(context: UpdateDiagnosticsContext, *, phase: str) -> None:
    if _report_names(context.location):
        return
    write_update_diagnostics_report(
        context,
        {
            "classification": "interrupted_preparation",
            "phase": phase,
            "check": None,
            "entry": None,
            "attempt": None,
            "error": None,
        },
    )


def release_update_diagnostics(base_path: str, context: UpdateDiagnosticsContext) -> None:
    if os.path.isdir(context.location) and _report_names(context.location):
        return
    verify_update_diagnostics_preserved(context)
    os.remove(os.path.join(context.location, RECEIPT_FILENAME))
    fsync_directory(context.location, strict=True)
    locator_path = update_diagnostics_locator_path(base_path, context.task_id)
    if os.path.lexists(locator_path):
        os.remove(locator_path)
        fsync_directory(os.path.dirname(locator_path), strict=True)
    if os.path.isdir(context.location) and not os.listdir(context.location):
        os.rmdir(context.location)
        fsync_directory(os.path.dirname(context.location), strict=True)


def read_update_diagnostics_summary(base_path: str, task_id: str) -> UpdateDiagnosticsSummary:
    context = read_update_diagnostics_locator(base_path, task_id)
    if context is None:
        return not_recorded_update_diagnostics()
    names = _report_names(context.location)
    if os.path.lexists(os.path.join(context.location, RECEIPT_FILENAME)):
        verify_update_diagnostics_preserved(context)
    if not names:
        return not_recorded_update_diagnostics()
    latest = _read_report(context, names[-1])
    classification = latest.get("classification")
    if not isinstance(classification, str) or classification not in DIAGNOSTIC_CLASSIFICATIONS:
        raise StateError("Update diagnostics report does not match its operation.")
    return UpdateDiagnosticsSummary(
        "available",
        context.location,
        classification,
        read_update_diagnostics_reference(context),
    )
