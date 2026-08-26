"""SoAI - Backup licensing recovery manifest ownership [backend/app/backup/licensing_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Literal

from core.backup.paths import (
    get_backup_relative_database_path,
    get_backup_relative_encryption_key_path,
)
from core.backup.types import BackupManifestEntry
from core.errors.exceptions import ValidationError
from core.licensing.backup_recovery import (
    LicensingRecoverySummary,
    LicensingRecoveryTarget,
    snapshot_has_bound_licensing_state,
    validate_licensing_recovery_edition,
    validate_licensing_recovery_pair,
)
from core.licensing.trust_material import load_release_trust_material
from core.licensing.types import Edition
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields


def build_licensing_recovery_summary(
    backup_directory: str,
    files: Mapping[str, BackupManifestEntry | JSONValue],
    *,
    database_target_completed: bool,
) -> LicensingRecoverySummary:
    database_relative = get_backup_relative_database_path()
    encryption_relative = get_backup_relative_encryption_key_path()
    database_digest = _entry_digest(files.get(database_relative))
    encryption_digest = _entry_digest(files.get(encryption_relative))
    database_present = database_digest is not None
    encryption_present = encryption_digest is not None
    if database_present:
        bound = snapshot_has_bound_licensing_state(
            os.path.join(backup_directory, database_relative)
        )
        state: Literal["not_applicable", "complete", "incomplete"] = (
            "not_applicable" if not bound else "complete" if encryption_present else "incomplete"
        )
    else:
        state = (
            "incomplete"
            if encryption_present or not database_target_completed
            else "not_applicable"
        )
    return {
        "state": state,
        "database": {"present": database_present, "sha256": database_digest},
        "encryption_key": {"present": encryption_present, "sha256": encryption_digest},
    }


def licensing_recovery_is_restorable(value: JSONValue) -> bool:
    return _parse_summary(value)["state"] != "incomplete"


def validate_restore_licensing_pair(
    backup_directory: str,
    manifest: JSONDict,
    selected_files: JSONDict,
    project_root: str | None = None,
    *,
    expected_edition: Edition,
    live_database_path: str | None = None,
) -> None:
    summary = _parse_summary(manifest.get("licensing_recovery"))
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValidationError("Backup manifest files are invalid.")
    recomputed = build_licensing_recovery_summary(
        backup_directory,
        files,
        database_target_completed=True,
    )
    if summary != recomputed:
        raise ValidationError("Backup licensing recovery metadata does not match its files.")
    if recomputed["state"] == "incomplete":
        raise ValidationError("Backup licensing recovery pair is incomplete.")
    database_relative = get_backup_relative_database_path()
    encryption_relative = get_backup_relative_encryption_key_path()
    database_selected = _entry_digest(selected_files.get(database_relative)) is not None
    encryption_selected = _entry_digest(selected_files.get(encryption_relative)) is not None
    if database_selected != encryption_selected:
        if database_selected:
            validate_licensing_recovery_edition(
                os.path.join(backup_directory, database_relative),
                expected_edition,
            )
        selected_database_bound = database_selected and snapshot_has_bound_licensing_state(
            os.path.join(backup_directory, database_relative)
        )
        live_database_bound = (
            live_database_path is not None
            and os.path.isfile(live_database_path)
            and snapshot_has_bound_licensing_state(live_database_path)
        )
        if selected_database_bound or live_database_bound:
            raise ValidationError(
                "A one-half licensing recovery replacement cannot modify bound state."
            )
        return
    if not database_selected:
        return
    database_path = os.path.join(backup_directory, database_relative)
    encryption_path = os.path.join(backup_directory, encryption_relative)
    catalog = load_release_trust_material(project_root) if project_root is not None else None
    validate_licensing_recovery_pair(
        database_path,
        encryption_path,
        expected_edition,
        catalog,
    )


def _entry_digest(value: BackupManifestEntry | JSONValue) -> str | None:
    if not isinstance(value, dict) or value.get("type") != "file":
        return None
    digest = value.get("sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValidationError("Backup licensing recovery digest is invalid.")
    return digest


def _parse_summary(value: JSONValue) -> LicensingRecoverySummary:
    if not isinstance(value, dict):
        raise ValidationError("Backup manifest is missing licensing recovery metadata.")
    require_exact_json_fields(
        value,
        allowed_fields=("state", "database", "encryption_key"),
        label="Licensing recovery summary",
    )
    state = value.get("state")
    if state == "not_applicable":
        resolved_state: Literal["not_applicable", "complete", "incomplete"] = "not_applicable"
    elif state == "complete":
        resolved_state = "complete"
    elif state == "incomplete":
        resolved_state = "incomplete"
    else:
        raise ValidationError("Backup licensing recovery state is invalid.")
    return {
        "state": resolved_state,
        "database": _parse_target(value.get("database")),
        "encryption_key": _parse_target(value.get("encryption_key")),
    }


def _parse_target(value: JSONValue) -> LicensingRecoveryTarget:
    if not isinstance(value, dict):
        raise ValidationError("Backup licensing recovery target is invalid.")
    require_exact_json_fields(
        value,
        allowed_fields=("present", "sha256"),
        label="Licensing recovery target",
    )
    present = value.get("present")
    digest = value.get("sha256")
    if not isinstance(present, bool) or (
        digest is not None
        and (not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None)
    ):
        raise ValidationError("Backup licensing recovery target is invalid.")
    if present != (digest is not None):
        raise ValidationError("Backup licensing recovery target is contradictory.")
    return {"present": present, "sha256": digest}


__all__ = (
    "build_licensing_recovery_summary",
    "licensing_recovery_is_restorable",
    "validate_restore_licensing_pair",
)
