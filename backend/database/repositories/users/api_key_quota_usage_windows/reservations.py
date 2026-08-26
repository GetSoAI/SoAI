"""SoAI - Reservation workflow for API key quota windows [backend/database/repositories/users/api_key_quota_usage_windows/reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.quotas.api_key_quota_windows import (
    compute_reset_at_ms,
    normalize_api_key_quota_expected_mode,
)
from core.validation.epoch import require_unix_epoch_ms
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.users.api_key_quota_config import (
    normalize_quota_config_row,
    sync_get_quota_config_row,
)
from database.repositories.users.api_key_quota_usage_windows.state import (
    sync_get_quota_status,
)
from database.repositories.users.api_key_quota_usage_windows.window_support import (
    resolve_window_limits,
    sync_load_quota_window_row,
)
from database.repositories.users.api_keys.write_ops import (
    sync_record_rate_limited,
    sync_record_usage,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_reserve_quota_units",
    "sync_reserve_quota_units_for_mode",
    "sync_reserve_quota_units_for_mode_with_usage",
)

LOGGER_NAME = "SoAI.database.repositories.reservations"
OPERATION = "database.api_key_quotas.reserve_with_usage.record_usage"


def sync_reserve_quota_units(
    conn: sqlite3.Connection,
    key_id: str,
    estimate_units: int,
    now_ts_ms: int,
    reservation_ttl_ms: int,
) -> JSONDict:
    require_unix_epoch_ms(
        now_ts_ms,
        error_message="now_ts_ms must be an epoch-millisecond integer.",
    )
    estimate = int(estimate_units)
    if estimate < 0:
        raise ValidationError("estimate_units must be >= 0.")
    ttl_ms = max(0, int(reservation_ttl_ms))
    config_row = sync_get_quota_config_row(conn, key_id)
    config = normalize_quota_config_row(config_row)
    mode_value = config.get("mode")
    mode = mode_value if isinstance(mode_value, str) else "none"
    if mode not in {"tokens", "requests"}:
        return {"allowed": True, "reservation": None, "status": {"unit": "none"}}
    if config_row is None:
        raise StateError("Quota config row is missing after normalization.")
    updated_at_ms_value = config_row.get("updated_at_ms")
    config_updated_at_ms = coerce_int_from_sqlite(updated_at_ms_value) or 0
    window_limits, hourly_window_hours = resolve_window_limits(config)
    if not window_limits:
        return {"allowed": True, "reservation": None, "status": {"unit": mode}}
    windows_to_charge: list[str] = []
    limiting_window = None
    retry_at = None
    for name in ("hourly", "daily", "weekly", "monthly"):
        limit = window_limits.get(name)
        if limit is None:
            continue
        window_ms, start_ts_ms, used, reserved = sync_load_quota_window_row(
            conn,
            key_id=key_id,
            window_name=name,
            hourly_window_hours=hourly_window_hours,
            now_ts_ms=now_ts_ms,
        )
        projected = int(used) + int(reserved) + int(estimate)
        if projected > int(limit):
            limiting_window = name
            retry_at = compute_reset_at_ms(
                window_start_ts_ms=int(start_ts_ms),
                window_ms=int(window_ms),
            )
            break
        windows_to_charge.append(name)
    if limiting_window is not None:
        status = sync_get_quota_status(conn, key_id, now_ts_ms)
        sync_record_rate_limited(conn, key_id)
        return {
            "allowed": False,
            "reservation": None,
            "status": status,
            "window": limiting_window,
            "retry_at_ms": int(retry_at or now_ts_ms),
        }
    for name in windows_to_charge:
        conn.execute(
            """
            UPDATE openai_api_key_quota_usage_windows
            SET reserved_units = reserved_units + ?, updated_at_ms = ?
            WHERE key_id = ? AND window_name = ?
            """,
            (int(estimate), int(now_ts_ms), key_id, name),
        )
    reservation_id = f"quota_reservation_{uuid.uuid4().hex}"
    expires_at_ms = int(now_ts_ms) + int(ttl_ms)
    for window_name in windows_to_charge:
        conn.execute(
            """
            INSERT INTO openai_api_key_quota_reservations (
                reservation_id,
                key_id,
                window_name,
                estimate_units,
                reserved_at_ms,
                expires_at_ms,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, 'reserved')
            """,
            (
                reservation_id,
                key_id,
                window_name,
                int(estimate),
                int(now_ts_ms),
                int(expires_at_ms),
            ),
        )
    reservation: JSONDict = {
        "reservation_id": reservation_id,
        "key_id": key_id,
        "mode": mode,
        "estimate_units": int(estimate),
        "windows": list(windows_to_charge),
        "reserved_at_ms": int(now_ts_ms),
        "config_updated_at_ms": int(config_updated_at_ms),
    }
    status_after = sync_get_quota_status(conn, key_id, now_ts_ms)
    return {"allowed": True, "reservation": reservation, "status": status_after}


def sync_reserve_quota_units_for_mode(
    conn: sqlite3.Connection,
    key_id: str,
    expected_mode: str,
    estimate_units: int,
    now_ts_ms: int,
    reservation_ttl_ms: int,
) -> JSONDict:
    normalized_expected_mode = normalize_api_key_quota_expected_mode(expected_mode)
    config_row = sync_get_quota_config_row(conn, key_id)
    config = normalize_quota_config_row(config_row)
    mode_value = config.get("mode")
    mode = mode_value if isinstance(mode_value, str) else "none"
    if mode != normalized_expected_mode:
        return {"allowed": True, "reservation": None, "status": {"unit": mode}}
    return sync_reserve_quota_units(
        conn,
        key_id,
        int(estimate_units),
        int(now_ts_ms),
        int(reservation_ttl_ms),
    )


def sync_reserve_quota_units_for_mode_with_usage(
    conn: sqlite3.Connection,
    key_id: str,
    expected_mode: str,
    estimate_units: int,
    now_ts_ms: int,
    reservation_ttl_ms: int,
    client_ip: str | None,
) -> JSONDict:
    resolved_ip = str(client_ip or "").strip() or None
    try:
        sync_record_usage(conn, key_id, int(now_ts_ms), resolved_ip)
    except sqlite3.Error as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to record API key usage during quota reservation (non-critical).",
            operation=OPERATION,
            details={"key_id": str(key_id)},
            level="debug",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="database.api_key_quotas.reserve_with_usage.record_usage",
            details={"key_id": str(key_id)},
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Unexpected error while recording API key usage during quota reservation (non-critical).",
            operation=OPERATION,
            details={"key_id": str(key_id)},
            level="error",
        )
    return sync_reserve_quota_units_for_mode(
        conn,
        key_id,
        expected_mode,
        int(estimate_units),
        int(now_ts_ms),
        int(reservation_ttl_ms),
    )
