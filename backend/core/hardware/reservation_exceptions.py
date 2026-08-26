"""SoAI - Disk reservation cleanup exception contracts [backend/core/hardware/reservation_exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import CancelledError

from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = (
    "DISK_RESERVATION_OPERATION_EXCEPTIONS",
    "close_write_claim_context",
    "preserve_primary_exception_cleanup_failure",
)


DISK_RESERVATION_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    OSError,
    RuntimeError,
    TimeoutError,
    UnicodeError,
    ValueError,
    CancelledError,
    *RECOVERABLE_EXCEPTIONS,
)


def preserve_primary_exception_cleanup_failure(
    primary_exception: BaseException | None,
    cleanup_exception: Exception,
    *,
    cleanup_action: str,
) -> None:
    if primary_exception is None:
        raise cleanup_exception
    primary_exception.add_note(f"{cleanup_action} failed: {cleanup_exception}")


def close_write_claim_context(
    *,
    closed: bool,
    primary_exception: BaseException | None,
    commit: Callable[[], None],
    rollback: Callable[[], None],
    commit_cleanup_action: str,
    rollback_cleanup_action: str,
) -> None:
    if closed:
        return
    if primary_exception is not None:
        try:
            commit()
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
            preserve_primary_exception_cleanup_failure(
                primary_exception,
                commit_exception,
                cleanup_action=commit_cleanup_action,
            )
        return
    try:
        rollback()
    except DISK_RESERVATION_OPERATION_EXCEPTIONS as rollback_exception:
        preserve_primary_exception_cleanup_failure(
            primary_exception,
            rollback_exception,
            cleanup_action=rollback_cleanup_action,
        )
