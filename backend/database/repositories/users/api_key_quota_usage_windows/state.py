"""SoAI - Quota status queries and window row bootstrap [backend/database/repositories/users/api_key_quota_usage_windows/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.quotas.api_key_quota_windows import compute_reset_at_ms
from core.validation.epoch import require_unix_epoch_ms
from database.repositories.users.api_key_quota_config import (
    normalize_quota_config_row,
    sync_get_quota_config_row,
)
from database.repositories.users.api_key_quota_usage_windows.window_support import (
    resolve_window_limits,
    sync_load_quota_window_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_get_quota_status",)


def sync_get_quota_status(conn: sqlite3.Connection, key_id: str, now_ts: int) -> JSONDict:
    require_unix_epoch_ms(
        now_ts,
        error_message="now_ts_ms must be an epoch-millisecond integer.",
    )
    config_row = sync_get_quota_config_row(conn, key_id)
    config = normalize_quota_config_row(config_row)
    mode_value = config.get("mode")
    mode = mode_value if isinstance(mode_value, str) else "none"
    status: JSONDict = {"unit": mode}
    if mode not in {"tokens", "requests"}:
        return status
    window_limits, hourly_window_hours = resolve_window_limits(config)
    for name in ("hourly", "daily", "weekly", "monthly"):
        limit = window_limits.get(name)
        if limit is None:
            status[name] = None
            continue
        window_ms, start_ts_ms, used, reserved = sync_load_quota_window_row(
            conn,
            key_id=key_id,
            window_name=name,
            hourly_window_hours=hourly_window_hours,
            now_ts_ms=now_ts,
        )
        remaining = max(0, int(limit) - int(used) - int(reserved))
        status[name] = {
            "limit_units": int(limit),
            "used_units": int(used),
            "reserved_units": int(reserved),
            "remaining_units": int(remaining),
            "window_start_ts_ms": int(start_ts_ms),
            "reset_at_ms": compute_reset_at_ms(
                window_start_ts_ms=int(start_ts_ms),
                window_ms=int(window_ms),
            ),
            "window_ms": int(window_ms),
        }
    return status
