"""SoAI - Essential-startup update activation commit [backend/app/updater/software_update/activation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.updater.software_update.activation_state import (
    activation_commit_lock_path,
    activation_process_path,
    activation_receipt_path,
    find_pending_update_activation,
)
from app.updater.software_update.install_transaction import finalize_update_transaction
from app.updater.software_update.install_transaction_state import AppliedUpdateTransaction
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.runtime.instance_record import (
    read_verified_runtime_instance_record,
    runtime_record_matches_current_process,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("commit_ready_update_activation",)


def commit_ready_update_activation(
    *,
    base_path: str,
    edition: str,
    product_version: str,
    config_path: str,
    repair_plane: bool,
    logger: LoggerProtocol,
) -> bool:
    with acquire_interprocess_lock(
        activation_commit_lock_path(base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        pending = find_pending_update_activation(base_path)
        if pending is None:
            return False
        if repair_plane:
            raise StateError(
                "The candidate requires essential startup repair and cannot commit its update."
            )
        if pending.edition != edition or pending.to_version != product_version:
            raise StateError(
                "Candidate edition or version does not match the installed update target."
            )
        if os.path.normcase(os.path.abspath(config_path)) != os.path.normcase(pending.config_path):
            raise StateError("Candidate configuration does not match the update's protected state.")
        record = read_verified_runtime_instance_record(
            activation_process_path(pending.paths),
            base_dir=base_path,
            expected_edition=edition,
            expected_pid=os.getpid(),
        )
        if record is None or not runtime_record_matches_current_process(
            record,
            base_dir=base_path,
            expected_edition=edition,
        ):
            raise StateError("Candidate activation process identity is unavailable or mismatched.")
        if not finalize_update_transaction(
            transaction=AppliedUpdateTransaction(base_path, pending.paths.transaction_path),
            update_success=True,
            logger=logger,
        ):
            raise StateError("Candidate update could not durably commit activation.")
        if not os.path.isfile(activation_receipt_path(pending)):
            raise StateError("Activation committed but result publication requires repair.")
        return True
