"""SoAI - Config scan failure backoff logic [backend/app/config/reconciliation_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.types import ScanReadFailure

__all__ = (
    "record_failed_read",
    "should_retry_failed_read",
)


def should_retry_failed_read(
    scan_read_failures: dict[str, ScanReadFailure],
    path: str,
    *,
    now: float,
) -> bool:
    entry = scan_read_failures.get(path)
    if entry is None:
        return True
    return now >= entry.next_retry_at


def record_failed_read(
    scan_read_failures: dict[str, ScanReadFailure],
    scan_failure_cls: type[ScanReadFailure],
    *,
    path: str,
    now: float,
    error_signature: str,
    transient_lock: bool,
) -> bool:
    existing = scan_read_failures.get(path)
    if existing is None:
        delay = 0.5 if transient_lock else 2.0
        scan_read_failures[path] = scan_failure_cls(
            next_retry_at=now + delay,
            delay_seconds=delay,
            error_signature=error_signature,
        )
        return not transient_lock
    should_publish = error_signature != existing.error_signature and (not transient_lock)
    new_delay = min(existing.delay_seconds * 2.0, 60.0)
    if transient_lock:
        new_delay = min(new_delay, 5.0)
    scan_read_failures[path] = scan_failure_cls(
        next_retry_at=now + new_delay,
        delay_seconds=new_delay,
        error_signature=error_signature,
    )
    return should_publish
