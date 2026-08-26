"""SoAI - Quota reservation finalization for API key usage windows [backend/database/repositories/users/api_key_quota_usage_windows/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.quotas.api_key_quota_windows import resolve_window_ms
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.users.api_key_quota_config import (
    normalize_quota_config_row,
    sync_get_quota_config_row,
)
from database.repositories.users.api_key_quota_usage_windows.window_support import (
    normalize_reservation_windows,
    resolve_reservation_id,
    sync_ensure_quota_window_row,
    sync_try_mark_reservation_finalized,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_finalize_quota_reservation",)


def sync_finalize_quota_reservation(
    conn: sqlite3.Connection,
    key_id: str,
    reservation: JSONDict,
    actual_units: int,
    now_ts: int,
) -> None:
    require_unix_epoch_ms(now_ts, error_message="now_ts must be an epoch-millisecond integer.")
    reservation_id_value = reservation.get("reservation_id")
    reservation_id = resolve_reservation_id(reservation_id_value)
    if reservation_id is None:
        raise ValidationError("reservation_id is required.")
    windows = normalize_reservation_windows(reservation.get("windows"))
    if not windows:
        return
    estimate_value = reservation.get("estimate_units")
    estimate_candidate = coerce_optional_non_negative_int_strict(estimate_value)
    estimate = estimate_candidate if estimate_candidate is not None else 0
    estimate = max(0, estimate)
    actual = int(actual_units)
    actual = max(0, actual)
    reservation_mode_value = reservation.get("mode")
    reservation_mode = reservation_mode_value if isinstance(reservation_mode_value, str) else "none"
    should_charge = False
    hourly_window_hours = None
    config_row = sync_get_quota_config_row(conn, key_id)
    if config_row is not None:
        updated_at_value = config_row.get("updated_at_ms")
        config_updated_at_ms = coerce_int_from_sqlite(updated_at_value) or 0
        expected_updated_at_value = reservation.get("config_updated_at_ms")
        expected_updated_at_candidate = coerce_optional_non_negative_int_strict(
            expected_updated_at_value,
        )
        expected_updated_at_ms = (
            expected_updated_at_candidate
            if expected_updated_at_candidate is not None
            else config_updated_at_ms
        )
        if expected_updated_at_ms == config_updated_at_ms:
            config = normalize_quota_config_row(config_row)
            mode_value = config.get("mode")
            mode = mode_value if isinstance(mode_value, str) else "none"
            if mode in {"tokens", "requests"} and mode == reservation_mode:
                should_charge = True
                hourly_config_value = config.get("hourly")
                hourly_config = (
                    hourly_config_value if isinstance(hourly_config_value, dict) else None
                )
                if hourly_config is not None:
                    hours_raw = hourly_config.get("window_hours")
                    hourly_window_hours = coerce_optional_non_negative_int_strict(hours_raw)
    used_increment = actual if should_charge else 0
    finalized = sync_try_mark_reservation_finalized(
        conn,
        reservation_id=reservation_id,
        key_id=key_id,
        finalized_at_ms=now_ts,
        charged_units=used_increment,
        released_units=estimate,
    )
    if not finalized:
        return
    for window_name in windows:
        if should_charge:
            window_ms = resolve_window_ms(
                window_name=window_name,
                hourly_window_hours=hourly_window_hours,
            )
            sync_ensure_quota_window_row(
                conn,
                key_id=key_id,
                window_name=window_name,
                window_ms=window_ms,
                now_ts_ms=now_ts,
            )
        conn.execute(
            """
            UPDATE openai_api_key_quota_usage_windows
            SET reserved_units = MAX(0, reserved_units - ?),
                used_units = used_units + ?,
                updated_at_ms = ?
            WHERE key_id = ? AND window_name = ?
            """,
            (int(estimate), int(used_increment), int(now_ts), key_id, window_name),
        )
    conn.execute(
        """
        UPDATE openai_api_key_quota_reservations
        SET status = ?,
            finalized_at_ms = ?,
            charged_units = ?,
            released_units = ?
        WHERE reservation_id = ? AND key_id = ?
        """,
        (
            "finalized",
            int(now_ts),
            int(used_increment),
            int(estimate),
            reservation_id,
            key_id,
        ),
    )
