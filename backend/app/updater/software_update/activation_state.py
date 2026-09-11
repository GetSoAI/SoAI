"""SoAI - Pending update activation identity and recovery evidence [backend/app/updater/software_update/activation_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from app.installation_transaction_admission import (
    TRANSACTION_PREFIX,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_state import (
    ACTIVATION_FAILED_MARKER,
    NEW_COMPLETE_MARKER,
    OLD_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    AppliedUpdateTransaction,
    UpdateTransactionPaths,
    marker_path,
    paths_from_transaction_directory,
    validate_transaction_markers,
    write_marker,
)
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exceptions import StateError
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import read_regular_file_no_symlink
from core.licensing.edition import require_licensing_edition
from core.meta.paths import join_data_abs
from core.meta.versioning import parse_semantic_version
from core.runtime.instance_record import (
    RuntimeInstanceRecord,
    canonicalize_runtime_base_dir,
    read_runtime_instance_record,
    read_verified_runtime_instance_record,
    write_runtime_instance_record,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.software_update_result import write_software_update_result
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.types.json import JSONDict
from core.validation.strings import coerce_required_non_empty_str

__all__ = (
    "ACTIVATION_PENDING_MARKER",
    "UpdateActivationIdentity",
    "activation_process_path",
    "activation_commit_lock_path",
    "activation_receipt_path",
    "claim_pending_update_activation",
    "find_pending_update_activation",
    "persist_committed_activation_result",
    "persist_failed_activation_result",
    "prepare_update_activation",
    "read_pending_update_activation",
    "read_update_activation_identity",
    "record_update_activation_identity",
    "require_update_candidate_stopped",
    "validate_update_recovery_evidence",
)

ACTIVATION_PENDING_MARKER = "activation_pending"
ACTIVATION_IDENTITY_FILENAME = "activation.json"
ACTIVATION_PROCESS_FILENAME = "activation_process.json"


@dataclass(frozen=True, slots=True)
class UpdateActivationIdentity:
    paths: UpdateTransactionPaths
    task_id: str
    edition: str
    from_version: str
    to_version: str
    config_path: str

    def to_mapping(self) -> JSONDict:
        return {
            "task_id": self.task_id,
            "edition": self.edition,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "config_path": self.config_path,
        }


def activation_commit_lock_path(base_path: str) -> str:
    return join_data_abs(base_path, "locks", "soai.update.activation.lock")


def activation_receipt_path(pending: UpdateActivationIdentity) -> str:
    return join_data_abs(
        pending.paths.base_path, "state", f"software-update-{pending.task_id}.activated.json"
    )


def activation_process_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(paths.transaction_path, ACTIVATION_PROCESS_FILENAME)


def read_pending_update_activation(
    paths: UpdateTransactionPaths,
) -> UpdateActivationIdentity | None:
    pending_path = marker_path(paths.transaction_path, ACTIVATION_PENDING_MARKER)
    if not os.path.lexists(pending_path):
        return None
    if (
        read_regular_file_no_symlink(pending_path, max_bytes=128)
        != ACTIVATION_PENDING_MARKER.encode()
    ):
        raise StateError("Update activation marker is corrupt; preserve it for repair.")
    return read_update_activation_identity(paths)


def read_update_activation_identity(paths: UpdateTransactionPaths) -> UpdateActivationIdentity:
    payload = parse_json_dict(
        read_regular_file_no_symlink(
            os.path.join(paths.transaction_path, ACTIVATION_IDENTITY_FILENAME), max_bytes=8192
        ),
        field="update activation identity",
        reject_duplicate_keys=True,
    )
    return _parse_activation_identity(paths, payload)


def require_update_candidate_stopped(paths: UpdateTransactionPaths) -> None:
    pending = read_pending_update_activation(paths)
    process_path = activation_process_path(paths)
    if pending is None or not os.path.lexists(process_path):
        return
    candidate = read_verified_runtime_instance_record(
        process_path, base_dir=paths.base_path, expected_edition=pending.edition
    )
    if candidate is not None:
        raise StateError("Candidate process is still running; recovery cannot replace its state.")


def _parse_activation_identity(
    paths: UpdateTransactionPaths, payload: JSONDict
) -> UpdateActivationIdentity:
    if set(payload) != {"task_id", "edition", "from_version", "to_version", "config_path"}:
        raise StateError("Update activation identity fields are invalid.")
    task_id = validate_optional_task_id(payload.get("task_id"))
    if task_id is None or task_id != payload.get("task_id"):
        raise StateError("Update activation task identity is not canonical.")
    edition = require_licensing_edition(
        coerce_required_non_empty_str(payload.get("edition"), label="activation edition")
    )
    from_version = coerce_required_non_empty_str(
        payload.get("from_version"), label="activation baseline"
    )
    to_version = coerce_required_non_empty_str(payload.get("to_version"), label="activation target")
    parse_semantic_version(from_version)
    parse_semantic_version(to_version)
    config_path = coerce_required_non_empty_str(
        payload.get("config_path"), label="activation configuration"
    )
    if config_path != os.path.abspath(config_path):
        raise StateError("Update activation configuration path must be absolute.")
    return UpdateActivationIdentity(paths, task_id, edition, from_version, to_version, config_path)


def record_update_activation_identity(
    paths: UpdateTransactionPaths,
    *,
    task_id: str,
    edition: str,
    from_version: str,
    to_version: str,
    config_path: str,
) -> None:
    identity = _parse_activation_identity(
        paths,
        {
            "task_id": task_id,
            "edition": edition,
            "from_version": from_version,
            "to_version": to_version,
            "config_path": config_path,
        },
    )
    try:
        atomic_create_text_content_exclusive(
            os.path.join(paths.transaction_path, ACTIVATION_IDENTITY_FILENAME),
            serialize_json_compact_stable_strict(identity.to_mapping()),
            ensure_parent=False,
            file_mode=0o600,
            fsync_parent_directory=True,
        )
    except FileExistsError as exception:
        if read_update_activation_identity(paths) != identity:
            raise StateError(
                "Update activation identity conflicts with the accepted operation."
            ) from exception


def prepare_update_activation(transaction: AppliedUpdateTransaction) -> None:
    paths = paths_from_transaction_directory(transaction.base_path, transaction.transaction_path)
    validate_transaction_markers(paths.transaction_path)
    if not all(
        os.path.isfile(marker_path(paths.transaction_path, marker))
        for marker in (
            OLD_COMPLETE_MARKER,
            NEW_COMPLETE_MARKER,
            ROLLBACK_REQUIRED_MARKER,
        )
    ) or any(
        os.path.lexists(marker_path(paths.transaction_path, marker))
        for marker in (SUCCESS_COMPLETE_MARKER, ACTIVATION_FAILED_MARKER)
    ):
        raise StateError("Only a completely installed uncommitted update may await activation.")
    read_update_activation_identity(paths)
    write_marker(paths.transaction_path, ACTIVATION_PENDING_MARKER)


def find_pending_update_activation(base_path: str) -> UpdateActivationIdentity | None:
    found: UpdateActivationIdentity | None = None
    for name in os.listdir(base_path):
        if not name.startswith(TRANSACTION_PREFIX):
            continue
        path = os.path.join(base_path, name)
        if os.path.islink(path) or not os.path.isdir(path):
            raise StateError("Update transaction storage is invalid; preserve it for repair.")
        pending = read_pending_update_activation(paths_from_transaction_directory(base_path, path))
        if pending is None:
            continue
        if found is not None:
            raise StateError("Multiple updates await activation; preserve them for repair.")
        found = pending
    return found


def claim_pending_update_activation(base_path: str, record: RuntimeInstanceRecord) -> None:
    with acquire_interprocess_lock(
        activation_commit_lock_path(base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        pending = find_pending_update_activation(base_path)
        if pending is None:
            return
        if (
            pending.edition != record.edition
            or canonicalize_runtime_base_dir(pending.paths.base_path) != record.base_dir
        ):
            raise StateError("Candidate process does not match its pending update installation.")
        validate_transaction_markers(pending.paths.transaction_path)
        if os.path.exists(marker_path(pending.paths.transaction_path, ACTIVATION_FAILED_MARKER)):
            raise StateError("Candidate activation failed; restore the update before startup.")
        if require_rollback_inventory(pending.paths, old_complete=True) is None:
            raise StateError("Pending activation is missing its required rollback inventory.")
        path = activation_process_path(pending.paths)
        if os.path.lexists(path):
            raise StateError(
                "An earlier candidate requires update recovery before another startup."
            )
        write_runtime_instance_record(path, record)
        verified = read_verified_runtime_instance_record(
            path, base_dir=base_path, expected_edition=pending.edition, expected_pid=os.getpid()
        )
        if verified != record:
            raise StateError("Candidate update process identity could not be verified.")


def validate_update_recovery_evidence(paths: UpdateTransactionPaths) -> None:
    validate_transaction_markers(paths.transaction_path)
    pending = read_pending_update_activation(paths)
    if pending is None and os.path.lexists(
        marker_path(paths.transaction_path, ACTIVATION_FAILED_MARKER)
    ):
        raise StateError(
            "Update activation failure has no pending identity; preserve it for repair."
        )
    if pending is None and os.path.lexists(activation_process_path(paths)):
        raise StateError("Update process claim has no pending activation; preserve it for repair.")
    if not os.path.lexists(os.path.join(paths.transaction_path, ACTIVATION_IDENTITY_FILENAME)):
        return
    identity = read_update_activation_identity(paths)
    committed = os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER))
    receipt_path = activation_receipt_path(identity)
    if not committed and not os.path.lexists(receipt_path):
        return
    if not committed or read_pending_update_activation(paths) != identity:
        raise StateError("Update activation commit evidence conflicts; preserve it for repair.")
    record = read_runtime_instance_record(activation_process_path(paths))
    if record.edition != identity.edition or record.base_dir != canonicalize_runtime_base_dir(
        paths.base_path
    ):
        raise StateError("Committed update activation identity is inconsistent.")
    if os.path.lexists(receipt_path) and read_runtime_instance_record(receipt_path) != record:
        raise StateError("Update activation receipt conflicts with its committed process.")


def persist_committed_activation_result(paths: UpdateTransactionPaths) -> None:
    validate_update_recovery_evidence(paths)
    pending = read_pending_update_activation(paths)
    if pending is None:
        return
    if not os.path.isfile(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
        raise StateError("An update cannot publish completion before durable activation commit.")
    record = read_runtime_instance_record(activation_process_path(paths))
    write_software_update_result(
        paths.base_path,
        task_id=pending.task_id,
        from_version=pending.from_version,
        to_version=pending.to_version,
        status="completed",
        message=f"Updated to v{pending.to_version}",
    )
    write_runtime_instance_record(activation_receipt_path(pending), record)


def persist_failed_activation_result(paths: UpdateTransactionPaths) -> None:
    if not os.path.lexists(os.path.join(paths.transaction_path, ACTIVATION_IDENTITY_FILENAME)):
        return
    pending = read_update_activation_identity(paths)
    if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
        raise StateError("A committed activation cannot be reported as a failed update.")
    write_software_update_result(
        paths.base_path,
        task_id=pending.task_id,
        from_version=pending.from_version,
        to_version=pending.to_version,
        status="failed",
        message="The update was interrupted before activation. The previous installation was retained or restored.",
    )
