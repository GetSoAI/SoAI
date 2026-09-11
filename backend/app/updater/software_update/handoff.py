"""SoAI - Process-bound software update preparation handoff [backend/app/updater/software_update/handoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import psutil

from app.updater.software_update.install_transaction_recovery import (
    recover_interrupted_update_transactions,
)
from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.meta.paths import join_data_abs
from core.runtime.instance_record import (
    create_runtime_instance_record,
    read_verified_runtime_instance_record,
    runtime_record_matches_process_tree,
    write_runtime_instance_record,
)
from core.runtime.process_identity_kill import force_kill_process_tree_matching_identity_blocking
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.software_update_result import read_software_update_result
from core.timing.constants import (
    CONTROL_TIMEOUT_SEC,
    EXTENDED_TIMEOUT_SEC,
    MODERATE_DELAY_SEC,
    SETUP_TIMEOUT_SEC,
)
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "abort_unaccepted_updater",
    "accept_prepared_updater",
    "announce_prepared_updater",
    "clear_updater_handoff",
    "updater_handoff_record_path",
    "wait_for_prepared_updater",
)


def abort_unaccepted_updater(
    process_handle: ManagedProcess,
    base_path: str,
    task_id: str | None,
    logger: LoggerProtocol,
) -> None:
    if task_id is None:
        raise StateError("Updater cleanup requires its durable task identity.")
    if process_handle.poll() is None:
        try:
            created = read_process_create_time_ms(psutil.Process(process_handle.pid))
        except psutil.NoSuchProcess:
            process_handle.wait(timeout=CONTROL_TIMEOUT_SEC)
        except psutil.Error as exception:
            raise StateError(
                "Updater cleanup could not verify its process identity."
            ) from exception
        else:
            result = force_kill_process_tree_matching_identity_blocking(
                process_handle.pid, created, "unaccepted software updater", logger
            )
            if not result.success:
                raise StateError("Updater process cleanup requires repair; evidence was retained.")
        process_handle.wait(timeout=CONTROL_TIMEOUT_SEC)
    if not recover_interrupted_update_transactions(base_path, logger, allow_restoration=False):
        raise StateError("Updater preparation cleanup requires repair; evidence was retained.")
    clear_updater_handoff(base_path, task_id)


def updater_handoff_record_path(base_path: str, task_id: str) -> str:
    identity = validate_optional_task_id(task_id, field_name="Update handoff task identity")
    if identity is None or identity != task_id:
        raise StateError("Update handoff task identity must be canonical.")
    return join_data_abs(base_path, "state", f"software-update-{identity}.ready.json")


def accept_prepared_updater(base_path: str, task_id: str) -> None:
    atomic_write_text_content(
        f"{updater_handoff_record_path(base_path, task_id)}.accepted",
        task_id,
        fsync=True,
        fsync_parent_directory=True,
        file_mode=0o600,
    )


def announce_prepared_updater(*, base_path: str, task_id: str, edition: str) -> None:
    path = updater_handoff_record_path(base_path, task_id)
    if os.path.lexists(path) or os.path.lexists(f"{path}.accepted"):
        raise StateError("Update handoff evidence already exists; preserve it for repair.")
    record = create_runtime_instance_record(pid=os.getpid(), base_dir=base_path, edition=edition)
    write_runtime_instance_record(path, record)
    deadline = deadline_after(EXTENDED_TIMEOUT_SEC)
    while not deadline.expired():
        accepted = (
            read_regular_file_no_symlink(f"{path}.accepted", max_bytes=128)
            if os.path.lexists(f"{path}.accepted")
            else None
        )
        if accepted is not None:
            if accepted != task_id.encode("utf-8"):
                raise StateError("Updater preparation acknowledgement has an invalid identity.")
            return
        sleep_seconds(MODERATE_DELAY_SEC)
    raise StateError("Updater preparation was not acknowledged; installation was not started.")


async def wait_for_prepared_updater(
    *,
    base_path: str,
    task_id: str,
    edition: str,
    process_handle: ManagedProcess,
) -> bool:
    path = updater_handoff_record_path(base_path, task_id)
    if process_handle.poll() is not None:
        raise StateError("Updater exited before confirming preparation.")
    expected = create_runtime_instance_record(
        pid=process_handle.pid, base_dir=base_path, edition=edition
    )
    deadline = deadline_after(SETUP_TIMEOUT_SEC)
    while not deadline.expired():
        result = await asyncio.to_thread(read_software_update_result, base_path)
        if result is not None and result.task_id == task_id:
            if result.status == "cancelled":
                return False
            if result.status == "failed":
                raise StateError("Updater preparation failed; the application remains running.")
        if process_handle.poll() is not None:
            raise StateError("Updater exited before confirming preparation.")
        record = await asyncio.to_thread(
            read_verified_runtime_instance_record,
            path,
            base_dir=base_path,
            expected_edition=edition,
        )
        if record is not None:
            if not runtime_record_matches_process_tree(record, expected):
                raise ValidationError("Updater readiness does not belong to the launched process.")
            return True
        await asyncio.sleep(MODERATE_DELAY_SEC)
    raise StateError("Updater preparation timed out; the application remains running.")


def clear_updater_handoff(base_path: str, task_id: str) -> None:
    path = updater_handoff_record_path(base_path, task_id)
    for owned_path in (path, f"{path}.accepted"):
        try:
            os.unlink(owned_path)
        except FileNotFoundError:
            continue
    if os.path.isdir(os.path.dirname(path)):
        fsync_directory(os.path.dirname(path), strict=True)
