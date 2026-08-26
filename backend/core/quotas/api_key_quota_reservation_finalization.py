"""SoAI - Cancellation-safe quota reservation finalization helpers [backend/core/quotas/api_key_quota_reservation_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError, SoAITimeoutError
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.types.json import JSONDict

__all__ = ("finalize_quota_reservation_required",)

OPERATION = "core.quotas.api_key_quota_reservation_finalization.finalize_quota_reservation_required"
QUOTA_FINALIZATION_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    DatabaseError,
    SoAITimeoutError,
    TimeoutError,
)


async def finalize_quota_reservation_required(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    key_id: str,
    reservation: JSONDict,
    actual_units: int,
    logger: StandardLogger,
    trace_id: str | None,
    operation: str,
    attempts: int = 3,
) -> None:
    normalized_attempts = require_positive_int_strict(
        attempts,
        error_message="Quota finalization attempts must be a positive integer.",
    )
    key_id_value = str(key_id or "").strip()
    reservation_id_value = reservation.get("reservation_id")
    reservation_id = (
        reservation_id_value
        if isinstance(reservation_id_value, str) and reservation_id_value
        else None
    )
    reservation_path_value = reservation.get("path")
    reservation_path = (
        reservation_path_value
        if isinstance(reservation_path_value, str) and reservation_path_value
        else None
    )
    estimate_value = reservation.get("estimate_units")
    estimate_units = int(estimate_value) if is_strict_int(estimate_value) else None
    normalized_actual_units = require_non_negative_int_strict(
        actual_units,
        error_message="Quota finalization actual units must be a non-negative integer.",
    )
    if estimate_units is not None and 0 < estimate_units < normalized_actual_units:
        log_exception(
            logger,
            coerce_to_soai_error(
                ValueError("Quota finalization actual units exceed estimate."),
                operation=operation,
                details={
                    "key_id": key_id_value,
                    "reservation_id": reservation_id,
                    "path": reservation_path,
                    "actual_units": int(normalized_actual_units),
                    "estimate_units": int(estimate_units),
                },
            ),
            message="Quota finalization clamped actual units to reservation estimate.",
            trace_id=trace_id,
            operation=OPERATION,
            details={
                "key_id": key_id_value,
                "reservation_id": reservation_id,
                "path": reservation_path,
                "actual_units": int(normalized_actual_units),
                "estimate_units": int(estimate_units),
            },
            level="warning",
        )
        normalized_actual_units = int(estimate_units)
    for attempt_index in range(normalized_attempts):
        now_ts = epoch_ms()
        try:
            await uncancel_then_cleanup(
                database_api_keys.finalize_quota_reservation(
                    key_id_value,
                    reservation,
                    actual_units=int(normalized_actual_units),
                    now_ts=int(now_ts),
                ),
            )
            return
        except QUOTA_FINALIZATION_RETRY_EXCEPTIONS as exception:
            is_last_attempt = attempt_index >= (normalized_attempts - 1)
            log_exception(
                logger,
                exception,
                message=(
                    "Failed to finalize quota reservation; will retry."
                    if not is_last_attempt
                    else "Failed to finalize quota reservation."
                ),
                trace_id=trace_id,
                operation=OPERATION,
                details={
                    "key_id": key_id_value,
                    "reservation_id": reservation_id,
                    "path": reservation_path,
                },
                level="debug" if not is_last_attempt else "warning",
            )
            if is_last_attempt:
                raise
            delay = compute_exponential_backoff_seconds(
                attempt_index,
                base_seconds=0.05,
                maximum_seconds=0.5,
            )
            await asyncio.sleep(delay)
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                logger,
                coerced,
                message="Failed to finalize quota reservation (unexpected).",
                trace_id=trace_id,
                operation=OPERATION,
                details={
                    "key_id": key_id_value,
                    "reservation_id": reservation_id,
                    "path": reservation_path,
                },
                level="error",
            )
            raise coerced from exception
