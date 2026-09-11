"""SoAI - Software update process lock [backend/app/updater/software_update/update_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from app.installation_transaction_admission import INSTALLATION_TRANSACTION_LOCK_FILENAME
from core.bootstrap.lock import acquire_interprocess_lock
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import (
    atomic_text_write_temporary_paths,
    atomic_write_text_content,
)
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.meta.paths import join_data_abs
from core.runtime.instance_record import (
    RuntimeInstanceRecord,
    create_runtime_instance_record,
    read_runtime_instance_record,
    read_verified_runtime_instance_record,
    write_runtime_instance_record,
)
from core.system.pid_liveness import pid_is_running
from core.timing.constants import CONTROL_TIMEOUT_SEC, EXTENDED_TIMEOUT_SEC, MODERATE_DELAY_SEC
from core.timing.epoch import epoch_seconds_float
from core.timing.sleep import sleep_seconds

__all__ = (
    "guarded_software_update_lock",
    "guarded_software_update_recovery",
    "resolve_software_update_lock_dir",
    "require_software_update_lock_owner",
    "transfer_software_update_lock",
)

OPERATION_LOCK_PREPARE = "application_updater.run_software_update.prepare_lock"
OPERATION_LOCK_STALE_CLEANUP = "application_updater.run_software_update.stale_lock_cleanup"
LOCK_PUBLICATION_EXCEPTIONS = (OSError,) + RECOVERABLE_EXCEPTIONS


def resolve_software_update_lock_dir(base_path: str) -> str:
    return join_data_abs(base_path, "locks", "soai.update.lock.d")


def _pid_path(lock_dir: str) -> str:
    return os.path.join(lock_dir, "pid")


def _read_lock_identity(
    lock_dir: str, *, require_matching_pid: bool = True
) -> RuntimeInstanceRecord | None:
    record_path = os.path.join(lock_dir, "process.json")
    owner_pid = _read_lock_pid(lock_dir)
    if os.path.lexists(_pid_path(lock_dir)) and owner_pid is None:
        raise StateError("Update PID ownership evidence is invalid; preserve it for repair.")
    if not os.path.lexists(record_path):
        return None
    if os.path.islink(record_path) or not os.path.isfile(record_path):
        raise StateError("Update process ownership evidence is invalid; preserve it for repair.")
    record = read_runtime_instance_record(record_path)
    if os.path.normcase(resolve_software_update_lock_dir(record.base_dir)) != os.path.normcase(
        lock_dir
    ) or (require_matching_pid and record.pid != owner_pid):
        raise StateError(
            "Update process ownership evidence is inconsistent; preserve it for repair."
        )
    return record


def require_software_update_lock_owner(
    lock_dir: str, *, base_path: str, edition: str, expected_pid: int
) -> None:
    if (
        os.path.islink(lock_dir)
        or not os.path.isdir(lock_dir)
        or os.path.islink(_pid_path(lock_dir))
    ):
        raise StateError("Update ownership storage is invalid; preserve it for repair.")
    record = _read_lock_identity(lock_dir)
    if (
        record is None
        or read_verified_runtime_instance_record(
            os.path.join(lock_dir, "process.json"),
            base_dir=base_path,
            expected_edition=edition,
            expected_pid=expected_pid,
        )
        is None
    ):
        raise StateError("The expected live process does not own this software update lock.")


def _owner_is_running(lock_dir: str, owner_pid: int) -> bool:
    record = _read_lock_identity(lock_dir, require_matching_pid=False)
    if record is None:
        return pid_is_running(owner_pid)
    return (
        read_verified_runtime_instance_record(
            os.path.join(lock_dir, "process.json"),
            base_dir=record.base_dir,
            expected_edition=record.edition,
            expected_pid=owner_pid,
        )
        is not None
    )


def _read_lock_pid(lock_dir: str) -> int | None:
    pid_file = _pid_path(lock_dir)
    if not os.path.isfile(pid_file):
        return None
    try:
        with open_text(pid_file, encoding="utf-8", errors="replace") as file_handle:
            raw_value = file_handle.read().strip()
    except OSError:
        return None
    if not raw_value.isdigit():
        return None
    pid_value = int(raw_value)
    if pid_value <= 0:
        return None
    return pid_value


def _lock_without_pid_is_stale(lock_dir: str) -> bool:
    try:
        lock_age_seconds = epoch_seconds_float() - os.path.getmtime(lock_dir)
    except OSError:
        return False
    return lock_age_seconds > EXTENDED_TIMEOUT_SEC


def _remove_stale_lock(lock_dir: str, logger: LoggerProtocol) -> None:
    try:
        pid_file = _pid_path(lock_dir)
        identity_path = os.path.join(lock_dir, "process.json")
        owned = (
            identity_path,
            pid_file,
            *atomic_text_write_temporary_paths(identity_path),
            *atomic_text_write_temporary_paths(pid_file),
        )
        if set(os.listdir(lock_dir)).difference(os.path.basename(path) for path in owned):
            raise StateError("Update lock has unexpected contents; preserve it for repair.")
        existing = tuple(path for path in owned if os.path.lexists(path))
        if any(os.path.islink(path) or not os.path.isfile(path) for path in existing):
            raise StateError("Update lock cleanup found unsafe contents; preserve it for repair.")
        for path in existing:
            os.remove(path)
        os.rmdir(lock_dir)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to remove stale software update lock.",
            operation=OPERATION_LOCK_STALE_CLEANUP,
            details={"lock_dir": lock_dir},
            level="warning",
        )
        raise


def _publish_lock_owner(lock_dir: str, identity: RuntimeInstanceRecord) -> None:
    write_runtime_instance_record(os.path.join(lock_dir, "process.json"), identity)
    atomic_write_text_content(
        _pid_path(lock_dir),
        f"{identity.pid}\n",
        ensure_parent=False,
        fsync=True,
        fsync_parent_directory=True,
    )


def _try_acquire_lock(
    lock_dir: str, *, logger: LoggerProtocol, base_path: str, edition: str
) -> bool:
    try:
        os.mkdir(lock_dir, 0o700)
        try:
            identity = create_runtime_instance_record(
                pid=os.getpid(), base_dir=base_path, edition=edition
            )
            _publish_lock_owner(lock_dir, identity)
            return True
        except LOCK_PUBLICATION_EXCEPTIONS:
            _release_lock(lock_dir, logger)
            raise
    except FileExistsError as exception:
        if (
            os.path.islink(lock_dir)
            or not os.path.isdir(lock_dir)
            or os.path.islink(_pid_path(lock_dir))
        ):
            raise StateError(
                "Update ownership storage is invalid; preserve it for repair."
            ) from exception
        record = _read_lock_identity(lock_dir, require_matching_pid=False)
        pid_value = _read_lock_pid(lock_dir)
        if record is not None:
            if _owner_is_running(lock_dir, record.pid):
                return False
            if pid_value is not None and pid_value != record.pid and pid_is_running(pid_value):
                return False
        else:
            if pid_value is not None and _owner_is_running(lock_dir, pid_value):
                return False
            if pid_value is None and not _lock_without_pid_is_stale(lock_dir):
                return False
        _remove_stale_lock(lock_dir, logger)
        return False


def _release_lock(lock_dir: str, logger: LoggerProtocol) -> None:
    try:
        pid_file = _pid_path(lock_dir)
        record = _read_lock_identity(lock_dir, require_matching_pid=False)
        if record is not None or os.path.isfile(pid_file):
            owner_pid = record.pid if record is not None else _read_lock_pid(lock_dir)
            if owner_pid is None or owner_pid != os.getpid():
                return
            if not _owner_is_running(lock_dir, owner_pid):
                return
            identity_path = os.path.join(lock_dir, "process.json")
            if os.path.exists(identity_path):
                os.remove(identity_path)
            if os.path.exists(pid_file):
                os.remove(pid_file)
        if os.path.isdir(lock_dir):
            os.rmdir(lock_dir)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to release software update lock.",
            operation=OPERATION_LOCK_PREPARE,
            details={"lock_dir": lock_dir},
            level="warning",
        )


def transfer_software_update_lock(lock_dir: str, new_owner_pid: int) -> None:
    if new_owner_pid <= 0:
        raise StateError("Software update lock transfer received an invalid process ID.")
    with acquire_interprocess_lock(
        os.path.join(os.path.dirname(lock_dir), INSTALLATION_TRANSACTION_LOCK_FILENAME),
        timeout_sec=CONTROL_TIMEOUT_SEC,
    ):
        if _read_lock_pid(lock_dir) != os.getpid():
            raise StateError("Software update lock ownership changed before installer handoff.")
        record = _read_lock_identity(lock_dir)
        if record is None or not _owner_is_running(lock_dir, os.getpid()):
            raise StateError("Software update handoff requires verified process ownership.")
        child = create_runtime_instance_record(
            pid=new_owner_pid,
            base_dir=record.base_dir,
            edition=record.edition,
        )
        _publish_lock_owner(lock_dir, child)


@contextmanager
def guarded_software_update_lock(
    *,
    base_path: str,
    logger: LoggerProtocol,
    edition: str,
) -> Generator[None]:
    lock_dir = resolve_software_update_lock_dir(base_path)
    os.makedirs(os.path.dirname(lock_dir), exist_ok=True)
    deadline = deadline_after(EXTENDED_TIMEOUT_SEC)
    acquired = False
    try:
        while not deadline.expired():
            with acquire_interprocess_lock(
                os.path.join(os.path.dirname(lock_dir), INSTALLATION_TRANSACTION_LOCK_FILENAME),
                timeout_sec=CONTROL_TIMEOUT_SEC,
            ):
                acquired = _try_acquire_lock(
                    lock_dir, logger=logger, base_path=base_path, edition=edition
                )
            if acquired:
                break
            sleep_seconds(MODERATE_DELAY_SEC)
        if not acquired:
            raise StateError("A SoAI software update is already running.")
        yield
    finally:
        if acquired:
            with acquire_interprocess_lock(
                os.path.join(os.path.dirname(lock_dir), INSTALLATION_TRANSACTION_LOCK_FILENAME),
                timeout_sec=CONTROL_TIMEOUT_SEC,
            ):
                _release_lock(lock_dir, logger)


@contextmanager
def guarded_software_update_recovery(base_path: str) -> Generator[None]:
    with acquire_interprocess_lock(
        join_data_abs(base_path, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
        timeout_sec=CONTROL_TIMEOUT_SEC,
    ):
        lock_dir = resolve_software_update_lock_dir(base_path)
        if os.path.lexists(lock_dir):
            if (
                os.path.islink(lock_dir)
                or not os.path.isdir(lock_dir)
                or os.path.islink(_pid_path(lock_dir))
            ):
                raise StateError("Update ownership storage is invalid; preserve it for repair.")
            owner_pid = _read_lock_pid(lock_dir)
            record = _read_lock_identity(lock_dir, require_matching_pid=False)
            if record is not None:
                if owner_pid not in (None, record.pid, os.getpid()) and pid_is_running(owner_pid):
                    raise StateError("A live transfer owner prevents interrupted update recovery.")
                owner_pid = record.pid
            if owner_pid is None and not _lock_without_pid_is_stale(lock_dir):
                raise StateError("Update ownership is incomplete; preserve it for repair.")
            if (
                owner_pid is not None
                and owner_pid != os.getpid()
                and _owner_is_running(lock_dir, owner_pid)
            ):
                raise StateError(
                    "A live updater owns this installation; recovery was not attempted."
                )
        yield
