"""SoAI - Quota configuration operations for OpenAI API keys [backend/database/repositories/users/api_key_quota_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.quotas.api_key_quota_windows import (
    coerce_api_key_quota_positive_limit,
    normalize_api_key_quota_mode,
    normalize_api_key_quota_row_mode,
    normalize_hourly_window_hours,
    parse_api_key_quota_hourly_window_hours,
)
from core.types.json_value import coerce_json_dict
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "normalize_quota_config_row",
    "sync_get_quota_config_row",
    "sync_set_quota_config",
)


def normalize_quota_config_row(row: SQLiteRowDict | None) -> JSONDict:
    config: JSONDict = {"mode": "none"}
    if not row:
        return config
    config["mode"] = normalize_api_key_quota_row_mode(row.get("mode"))
    hourly_limit = coerce_int_from_sqlite(row.get("hourly_limit_units"))
    hourly_window_hours = coerce_int_from_sqlite(row.get("hourly_window_hours"))
    if hourly_limit is not None and hourly_window_hours is not None:
        config["hourly"] = {
            "limit_units": hourly_limit,
            "window_hours": hourly_window_hours,
        }
    else:
        config["hourly"] = None
    for window_name, column_name in (
        ("daily", "daily_limit_units"),
        ("weekly", "weekly_limit_units"),
        ("monthly", "monthly_limit_units"),
    ):
        limit_units = coerce_int_from_sqlite(row.get(column_name))
        if limit_units is None:
            config[window_name] = None
        else:
            config[window_name] = {"limit_units": limit_units}
    return config


def sync_get_quota_config_row(conn: sqlite3.Connection, key_id: str) -> SQLiteRowDict | None:
    cursor = conn.execute("SELECT * FROM openai_api_key_quota_config WHERE key_id = ?", (key_id,))
    return sync_fetch_one_as_dict(cursor)


def _validate_non_decreasing_limits(
    *,
    hourly: int | None,
    daily: int | None,
    weekly: int | None,
    monthly: int | None,
) -> None:
    ordered: list[tuple[str, int]] = []
    if hourly is not None:
        ordered.append(("hourly", hourly))
    if daily is not None:
        ordered.append(("daily", daily))
    if weekly is not None:
        ordered.append(("weekly", weekly))
    if monthly is not None:
        ordered.append(("monthly", monthly))
    previous_name = None
    previous_value = None
    for name, value in ordered:
        if previous_value is not None and value < previous_value:
            raise ValidationError(
                "Quota limits must be nondecreasing across windows.",
                details={"previous": previous_name, "current": name},
            )
        previous_name = name
        previous_value = value


def sync_set_quota_config(
    conn: sqlite3.Connection,
    key_id: str,
    payload: JSONDict,
    now_ts: int,
    reset_usage: bool,
    max_hourly_window_hours: int,
) -> JSONDict:
    exists_row = sync_fetch_one_as_dict(
        conn.execute("SELECT 1 AS found FROM openai_api_keys WHERE key_id = ? LIMIT 1", (key_id,)),
    )
    if not exists_row:
        raise StateError("OpenAI API key not found.")
    mode_value = payload.get("mode")
    mode = normalize_api_key_quota_mode(
        mode_value if isinstance(mode_value, str) else "none",
        empty_message="mode must be one of: none, tokens, requests.",
    )
    if mode == "none":
        conn.execute("DELETE FROM openai_api_key_quota_config WHERE key_id = ?", (key_id,))
        if reset_usage:
            conn.execute(
                "DELETE FROM openai_api_key_quota_usage_windows WHERE key_id = ?",
                (key_id,),
            )
            conn.execute(
                "DELETE FROM openai_api_key_quota_finalizations WHERE key_id = ?",
                (key_id,),
            )
            conn.execute(
                "DELETE FROM openai_api_key_quota_reservations WHERE key_id = ?",
                (key_id,),
            )
        return {"mode": "none", "hourly": None, "daily": None, "weekly": None, "monthly": None}
    hourly_payload = coerce_json_dict(payload.get("hourly"))
    daily_payload = coerce_json_dict(payload.get("daily"))
    weekly_payload = coerce_json_dict(payload.get("weekly"))
    monthly_payload = coerce_json_dict(payload.get("monthly"))
    hourly_limit = coerce_api_key_quota_positive_limit(hourly_payload, field_name="hourly")
    daily_limit = coerce_api_key_quota_positive_limit(daily_payload, field_name="daily")
    weekly_limit = coerce_api_key_quota_positive_limit(weekly_payload, field_name="weekly")
    monthly_limit = coerce_api_key_quota_positive_limit(monthly_payload, field_name="monthly")
    hourly_window_hours = None
    if hourly_payload is not None and "window_hours" in hourly_payload:
        hourly_window_hours = parse_api_key_quota_hourly_window_hours(
            hourly_payload.get("window_hours"),
        )
    hourly_window_hours = normalize_hourly_window_hours(
        hourly_window_hours,
        max_hours=int(max_hourly_window_hours),
    )
    if (hourly_limit is None) != (hourly_window_hours is None):
        raise ValidationError("hourly requires both limit_units and window_hours.")
    _validate_non_decreasing_limits(
        hourly=hourly_limit,
        daily=daily_limit,
        weekly=weekly_limit,
        monthly=monthly_limit,
    )
    existing_row = sync_get_quota_config_row(conn, key_id)
    previous_updated_at_ms = (
        coerce_int_from_sqlite(existing_row.get("updated_at_ms"))
        if existing_row is not None
        else None
    )
    previous_updated_at_ms_value = (
        int(previous_updated_at_ms) if isinstance(previous_updated_at_ms, int) else 0
    )
    effective_updated_at_ms = int(now_ts)
    if effective_updated_at_ms <= previous_updated_at_ms_value:
        effective_updated_at_ms = previous_updated_at_ms_value + 1
    conn.execute(
        """
        INSERT INTO openai_api_key_quota_config (
            key_id,
            mode,
            hourly_limit_units,
            hourly_window_hours,
            daily_limit_units,
            weekly_limit_units,
            monthly_limit_units,
            updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key_id) DO UPDATE SET
            mode = excluded.mode,
            hourly_limit_units = excluded.hourly_limit_units,
            hourly_window_hours = excluded.hourly_window_hours,
            daily_limit_units = excluded.daily_limit_units,
            weekly_limit_units = excluded.weekly_limit_units,
            monthly_limit_units = excluded.monthly_limit_units,
            updated_at_ms = excluded.updated_at_ms
        """,
        (
            key_id,
            mode,
            hourly_limit,
            hourly_window_hours,
            daily_limit,
            weekly_limit,
            monthly_limit,
            int(effective_updated_at_ms),
        ),
    )
    if reset_usage:
        conn.execute("DELETE FROM openai_api_key_quota_usage_windows WHERE key_id = ?", (key_id,))
        conn.execute("DELETE FROM openai_api_key_quota_finalizations WHERE key_id = ?", (key_id,))
        conn.execute("DELETE FROM openai_api_key_quota_reservations WHERE key_id = ?", (key_id,))
    row = sync_get_quota_config_row(conn, key_id)
    return normalize_quota_config_row(row)
