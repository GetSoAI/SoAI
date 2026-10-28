"""SoAI - Bounded waits for Windows sharing conflicts on managed files [backend/core/filesystem/windows_sharing_conflicts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections.abc import Callable, Iterable
from functools import cache, partial

from core.concurrency.deadlines import (
    MonotonicDeadline,
    deadline_after,
    earliest_deadline,
)
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError
from core.system.native_image_budget import native_image_allowance
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.timing.sleep import sleep_seconds

__all__ = (
    "ORDINARY_FILESYSTEM_SECONDS",
    "is_windows_sharing_conflict",
    "remove_path_with_sharing_retry",
    "rename_with_sharing_retry",
    "replace_with_sharing_retry",
    "retry_windows_sharing_conflicts",
    "sharing_conflict_deadline",
)

ORDINARY_FILESYSTEM_SECONDS = 30.0
INITIAL_RETRY_DELAY_SECONDS = 0.25
MAXIMUM_RETRY_DELAY_SECONDS = 2.0
RETRY_JITTER_RATIO = 0.1


def is_windows_sharing_conflict(exception: BaseException) -> bool:
    if sys.platform != "win32" or not isinstance(exception, OSError):
        return False
    try:
        native_code = exception.winerror
    except AttributeError:
        native_code = None
    return native_code in (32, 33)


def sharing_conflict_deadline(
    path: str, *, ceiling: MonotonicDeadline | None = None, planned_paths: Iterable[str] = ()
) -> MonotonicDeadline:
    allowance = native_image_allowance(
        ORDINARY_FILESYSTEM_SECONDS, roots=(path,), planned_paths=planned_paths
    )
    deadline = deadline_after(allowance.seconds)
    return earliest_deadline(deadline, ceiling) or deadline


def _path_identity(path: str) -> tuple[int, int, int] | None:
    try:
        status: os.stat_result | None = os.lstat(path)
    except FileNotFoundError:
        status = None
    if status is None:
        return None
    return status.st_dev, status.st_ino, stat.S_IFMT(status.st_mode)


def retry_windows_sharing_conflicts[Result](
    operation: Callable[[], Result],
    *,
    path: str | None,
    deadline: Callable[[], MonotonicDeadline],
    failure: OSError | None = None,
    cancellation: CancellationTokenProtocol | None = None,
    validate_identity: Callable[[], None] | None = None,
) -> Result:
    if path is None and validate_identity is None:
        raise StateError("A sharing retry requires an anchored identity validator or a path.")
    identity = _path_identity(path) if path is not None and validate_identity is None else None
    attempt = 0
    operation_deadline: MonotonicDeadline | None = None
    while True:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if failure is None:
            try:
                return operation()
            except OSError as exception:
                failure = exception
        if not is_windows_sharing_conflict(failure):
            raise failure
        if operation_deadline is None:
            operation_deadline = deadline()
        remaining = operation_deadline.remaining_seconds()
        if remaining <= 0:
            raise failure
        sleep_seconds(
            min(
                remaining,
                compute_exponential_backoff_seconds(
                    attempt,
                    base_seconds=INITIAL_RETRY_DELAY_SECONDS,
                    maximum_seconds=MAXIMUM_RETRY_DELAY_SECONDS,
                    jitter_ratio=RETRY_JITTER_RATIO,
                ),
            )
        )
        attempt += 1
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if validate_identity is not None:
            validate_identity()
        elif path is not None and _path_identity(path) != identity:
            raise StateError(
                "A managed file changed while waiting for another program to release it."
            ) from failure
        failure = None


def _bounded_deadline(
    path: str, ceiling: MonotonicDeadline | None
) -> Callable[[], MonotonicDeadline]:
    return cache(partial(sharing_conflict_deadline, path, ceiling=ceiling))


def rename_with_sharing_retry(
    source: str, destination: str, *, ceiling: MonotonicDeadline | None = None
) -> None:
    retry_windows_sharing_conflicts(
        partial(os.rename, source, destination),
        path=source,
        deadline=_bounded_deadline(source, ceiling),
    )


def replace_with_sharing_retry(
    source: str, destination: str, *, ceiling: MonotonicDeadline | None = None
) -> None:
    retry_windows_sharing_conflicts(
        partial(os.replace, source, destination),
        path=source,
        deadline=_bounded_deadline(source, ceiling),
    )


def _remove_owned_entry(function: Callable[[str], None], path: str) -> bool:
    removed = False
    try:
        function(path)
        removed = True
    except FileNotFoundError:
        removed = False
    return removed


def remove_path_with_sharing_retry(path: str, *, ceiling: MonotonicDeadline | None = None) -> None:
    deadline = _bounded_deadline(path, ceiling)
    if os.path.isdir(path) and not os.path.islink(path):

        def retry_failed_entry(
            function: Callable[[str], None], failed_path: str, exception: BaseException
        ) -> None:
            if function not in (os.remove, os.rmdir, os.unlink) or not isinstance(
                exception, OSError
            ):
                raise exception
            retry_windows_sharing_conflicts(
                partial(_remove_owned_entry, function, failed_path),
                path=failed_path,
                deadline=deadline,
                failure=exception,
            )

        shutil.rmtree(path, onexc=retry_failed_entry)
        return
    retry_windows_sharing_conflicts(
        partial(_remove_owned_entry, os.remove, path), path=path, deadline=deadline
    )
