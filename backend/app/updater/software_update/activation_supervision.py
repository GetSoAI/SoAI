"""SoAI - Candidate activation supervision and failed-start restoration [backend/app/updater/software_update/activation_supervision.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.updater.soai_instance import wait_for_instance_lock_release
from app.updater.soai_process import start_soai
from app.updater.software_update.activation_state import (
    UpdateActivationIdentity,
    activation_commit_lock_path,
    activation_process_path,
    activation_receipt_path,
    find_pending_update_activation,
)
from app.updater.software_update.install_transaction import finalize_update_transaction
from app.updater.software_update.install_transaction_state import (
    ACTIVATION_FAILED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    AppliedUpdateTransaction,
    marker_path,
    validate_transaction_markers,
    write_marker,
)
from core.bootstrap.lock import acquire_interprocess_lock
from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import StateError
from core.process.termination import (
    poll_process_exit_without_reaping,
    terminate_process_and_wait,
)
from core.runtime.instance_record import (
    RuntimeInstanceRecord,
    create_runtime_instance_record,
    read_runtime_instance_record,
    read_verified_runtime_instance_record,
    runtime_record_matches_process_tree,
)
from core.tasks.software_update_result import write_software_update_result
from core.timing.constants import CONTROL_TIMEOUT_SEC, MODERATE_DELAY_SEC, SETUP_TIMEOUT_SEC
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from app.updater.dependencies import SoftwareUpdateServiceDependencies
    from core.logging.protocols import LoggerProtocol
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "UpdateActivationCandidate",
    "start_update_activation",
    "wait_for_update_activation",
    "supervise_update_activation",
)


@dataclass(frozen=True, slots=True)
class UpdateActivationCandidate:
    pending: UpdateActivationIdentity
    process_handle: ManagedProcess | None
    expected: RuntimeInstanceRecord | None


def _has_committed_receipt(
    pending: UpdateActivationIdentity, expected: RuntimeInstanceRecord
) -> bool:
    try:
        receipt = read_runtime_instance_record(activation_receipt_path(pending))
    except FileNotFoundError:
        return False
    if not runtime_record_matches_process_tree(receipt, expected):
        raise StateError("Activation receipt does not identify the expected candidate process.")
    return True


def start_update_activation(
    pending: UpdateActivationIdentity,
    *,
    platform_name: str,
    main_py_path: str | None,
    logger: LoggerProtocol,
) -> UpdateActivationCandidate:
    with acquire_interprocess_lock(
        activation_commit_lock_path(pending.paths.base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        if find_pending_update_activation(pending.paths.base_path) != pending:
            raise StateError("Pending update activation changed before candidate startup.")
        validate_transaction_markers(pending.paths.transaction_path)
        if os.path.exists(marker_path(pending.paths.transaction_path, ACTIVATION_FAILED_MARKER)):
            raise StateError("Candidate activation failed; restore the update before startup.")
        if os.path.lexists(activation_process_path(pending.paths)):
            raise StateError("An earlier candidate requires recovery before another startup.")
        process_handle = start_soai(
            logger=logger,
            platform_name=platform_name,
            base_path=pending.paths.base_path,
            main_py_path=main_py_path,
            config_path=pending.config_path,
        )
        expected = None
        candidate_created = False
        try:
            if (
                process_handle is not None
                and poll_process_exit_without_reaping(process_handle) is None
            ):
                try:
                    expected = create_runtime_instance_record(
                        pid=process_handle.pid,
                        base_dir=pending.paths.base_path,
                        edition=pending.edition,
                    )
                except StateError:
                    if poll_process_exit_without_reaping(process_handle) is None:
                        raise
            candidate = UpdateActivationCandidate(pending, process_handle, expected)
            candidate_created = True
        finally:
            if not candidate_created and process_handle is not None:
                terminate_process_and_wait(
                    process_handle,
                    timeout_sec=CONTROL_TIMEOUT_SEC,
                    process_group=platform_name != "Windows",
                )
    return candidate


def wait_for_update_activation(
    candidate: UpdateActivationCandidate, *, logger: LoggerProtocol
) -> bool:
    pending = candidate.pending
    process_handle = candidate.process_handle
    expected = candidate.expected
    if process_handle is not None and expected is not None:
        deadline = deadline_after(SETUP_TIMEOUT_SEC)
        while not deadline.expired():
            if _has_committed_receipt(pending, expected):
                break
            if poll_process_exit_without_reaping(process_handle) is not None:
                break
            sleep_seconds(MODERATE_DELAY_SEC)
    with acquire_interprocess_lock(
        activation_commit_lock_path(pending.paths.base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        if expected is not None and _has_committed_receipt(pending, expected):
            return True
        validate_transaction_markers(pending.paths.transaction_path)
        if os.path.isfile(marker_path(pending.paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
            if expected is None or not runtime_record_matches_process_tree(
                read_runtime_instance_record(activation_process_path(pending.paths)), expected
            ):
                raise StateError("Committed activation does not identify the expected candidate.")
            logger.warning("Candidate activation committed; result publication requires recovery.")
            return True
        write_marker(pending.paths.transaction_path, ACTIVATION_FAILED_MARKER)
    return False


def supervise_update_activation(deps: SoftwareUpdateServiceDependencies) -> bool:
    pending = find_pending_update_activation(deps.base_path)
    if pending is None:
        raise StateError("Installed update is missing pending activation evidence.")
    candidate = start_update_activation(
        pending,
        platform_name=deps.platform_name,
        main_py_path=deps.main_py_path,
        logger=deps.logger,
    )
    activated = False
    try:
        activated = wait_for_update_activation(candidate, logger=deps.logger)
    finally:
        if not activated and candidate.process_handle is not None:
            terminate_process_and_wait(
                candidate.process_handle,
                timeout_sec=CONTROL_TIMEOUT_SEC,
                process_group=deps.platform_name != "Windows",
            )
    if activated:
        return True
    expected = candidate.expected
    with acquire_interprocess_lock(
        activation_commit_lock_path(deps.base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        process_path = activation_process_path(pending.paths)
        if (
            os.path.lexists(process_path)
            and read_verified_runtime_instance_record(
                process_path,
                base_dir=deps.base_path,
                expected_edition=pending.edition,
            )
            is not None
        ):
            raise StateError(
                "A candidate remains running; rollback requires verified process exit."
            )
        if not wait_for_instance_lock_release(logger=deps.logger, base_path=deps.base_path):
            raise StateError("Candidate instance lock remains held; rollback was not attempted.")
    if not finalize_update_transaction(
        transaction=AppliedUpdateTransaction(deps.base_path, pending.paths.transaction_path),
        update_success=False,
        logger=deps.logger,
    ):
        raise StateError("Candidate failed activation and rollback requires repair.")
    if expected is not None and _has_committed_receipt(pending, expected):
        return True
    write_software_update_result(
        deps.base_path,
        task_id=pending.task_id,
        from_version=pending.from_version,
        to_version=pending.to_version,
        status="failed",
        message="The candidate did not complete startup. The previous installation was restored.",
    )
    return False
