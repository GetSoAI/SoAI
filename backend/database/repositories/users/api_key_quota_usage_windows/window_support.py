"""SoAI - Shared quota window helpers for API key usage tracking [backend/database/repositories/users/api_key_quota_usage_windows/window_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.quotas.api_key_quota_windows import (
    WINDOW_NAMES,
    compute_reset_at_ms,
    resolve_window_ms,
)
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import (
    sync_fetch_changes_count,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ()


def sync_ensure_quota_window_row(
    conn: sqlite3.Connection,
    *,
    key_id: str,
    window_name: str,
    window_ms: int,
    now_ts_ms: int,
) -> tuple[int, int, int]:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT window_ms, window_start_at_ms, used_units, reserved_units
            FROM openai_api_key_quota_usage_windows
            WHERE key_id = ? AND window_name = ?
            """,
            (key_id, window_name),
        ),
    )
    if row is None:
        conn.execute(
            """
            INSERT INTO openai_api_key_quota_usage_windows (
                key_id,
                window_name,
                window_ms,
                window_start_at_ms,
                used_units,
                reserved_units,
                updated_at_ms
            ) VALUES (?, ?, ?, ?, 0, 0, ?)
            """,
            (key_id, window_name, int(window_ms), int(now_ts_ms), int(now_ts_ms)),
        )
        return (int(now_ts_ms), 0, 0)
    window_ms_value = coerce_required_int_from_sqlite_row(row, "window_ms")
    start_ts_ms = coerce_required_int_from_sqlite_row(row, "window_start_at_ms")
    used = coerce_required_int_from_sqlite_row(row, "used_units")
    reserved = coerce_required_int_from_sqlite_row(row, "reserved_units")
    if window_ms_value != int(window_ms) or now_ts_ms >= compute_reset_at_ms(
        window_start_ts_ms=start_ts_ms,
        window_ms=window_ms_value,
    ):
        conn.execute(
            """
            UPDATE openai_api_key_quota_usage_windows
            SET window_ms = ?, window_start_at_ms = ?, used_units = 0, reserved_units = 0, updated_at_ms = ?
            WHERE key_id = ? AND window_name = ?
            """,
            (int(window_ms), int(now_ts_ms), int(now_ts_ms), key_id, window_name),
        )
        return (int(now_ts_ms), 0, 0)
    return (start_ts_ms, used, reserved)


def sync_load_quota_window_row(
    conn: sqlite3.Connection,
    *,
    key_id: str,
    window_name: str,
    hourly_window_hours: int | None,
    now_ts_ms: int,
) -> tuple[int, int, int, int]:
    window_ms = resolve_window_ms(window_name=window_name, hourly_window_hours=hourly_window_hours)
    start_ts_ms, used, reserved = sync_ensure_quota_window_row(
        conn,
        key_id=key_id,
        window_name=window_name,
        window_ms=window_ms,
        now_ts_ms=now_ts_ms,
    )
    return (int(window_ms), int(start_ts_ms), int(used), int(reserved))


def resolve_window_limits(config: JSONDict) -> tuple[dict[str, int], int | None]:
    hourly_config_value = config.get("hourly")
    hourly_config = hourly_config_value if isinstance(hourly_config_value, dict) else None
    hourly_limit = None
    hourly_window_hours = None
    if hourly_config is not None:
        limit_raw = hourly_config.get("limit_units")
        hours_raw = hourly_config.get("window_hours")
        hourly_limit = coerce_optional_non_negative_int_strict(limit_raw)
        hourly_window_hours = coerce_optional_non_negative_int_strict(hours_raw)
    window_limits: dict[str, int] = {}
    if hourly_limit is not None and hourly_window_hours is not None:
        window_limits["hourly"] = hourly_limit
    for window_name in ("daily", "weekly", "monthly"):
        window_payload = config.get(window_name)
        if isinstance(window_payload, dict):
            limit_value = window_payload.get("limit_units")
            normalized_limit = coerce_optional_non_negative_int_strict(limit_value)
            if normalized_limit is not None:
                window_limits[window_name] = normalized_limit
    return (window_limits, hourly_window_hours)


def resolve_reservation_id(value: JSONValue) -> str | None:
    return coerce_optional_trimmed_str(value)


def normalize_reservation_windows(value: JSONValue) -> list[str]:
    if not isinstance(value, list):
        return []
    resolved_windows: list[str] = []
    seen_windows: set[str] = set()
    for window_name in value:
        if not isinstance(window_name, str):
            continue
        if window_name not in WINDOW_NAMES:
            continue
        if window_name in seen_windows:
            continue
        seen_windows.add(window_name)
        resolved_windows.append(window_name)
    return resolved_windows


def sync_try_mark_reservation_finalized(
    conn: sqlite3.Connection,
    *,
    reservation_id: str,
    key_id: str,
    finalized_at_ms: int,
    charged_units: int,
    released_units: int,
) -> bool:
    conn.execute(
        """
        INSERT INTO openai_api_key_quota_finalizations (
            reservation_id,
            key_id,
            finalized_at_ms,
            charged_units,
            released_units
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(reservation_id) DO NOTHING
        """,
        (
            reservation_id,
            key_id,
            int(finalized_at_ms),
            int(charged_units),
            int(released_units),
        ),
    )
    return sync_fetch_changes_count(conn) > 0
