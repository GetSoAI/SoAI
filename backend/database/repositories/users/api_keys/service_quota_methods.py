"""SoAI - API key repository quota methods [backend/database/repositories/users/api_keys/service_quota_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_AUTH
from database.repositories.users.api_key_quota_config import sync_set_quota_config
from database.repositories.users.api_key_quota_usage_windows.reservations import (
    sync_reserve_quota_units_for_mode,
    sync_reserve_quota_units_for_mode_with_usage,
)
from database.repositories.users.api_key_quota_usage_windows.state import (
    sync_get_quota_status,
)
from database.repositories.users.api_keys.internal_protocols import (
    DatabaseAPIKeysServiceProtocol,
)
from database.repositories.users.api_keys.quota_error_propagation import (
    raise_database_cause_if_needed,
)
from database.repositories.users.api_keys.quota_reads import get_quota_config

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_quota_config_method",
    "get_quota_status_method",
    "reserve_quota_units_for_mode_method",
    "set_quota_config_method",
)


async def get_quota_config_method(self: DatabaseAPIKeysServiceProtocol, key_id: str) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_quota_config(self.core, key_id)


async def set_quota_config_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    payload: JSONDict,
    *,
    reset_usage: bool = True,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    max_hourly_window_hours = int(
        self.config.get_int("API.OPENAI.KEY_QUOTAS.MAX_HOURLY_WINDOW_HOURS"),
    )
    try:
        return await self.core.writer.queue_write_operation(
            sync_set_quota_config,
            key_id,
            payload,
            epoch_ms(),
            bool(reset_usage),
            max_hourly_window_hours,
        )
    except DatabaseError as exception:
        raise_database_cause_if_needed(exception)


async def get_quota_status_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    now_ts: int,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    try:
        return await self.core.writer.queue_write_operation(
            sync_get_quota_status,
            key_id,
            int(now_ts),
        )
    except DatabaseError as exception:
        raise_database_cause_if_needed(exception)


async def reserve_quota_units_for_mode_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    expected_mode: str,
    estimate_units: int,
    now_ts: int,
    client_ip: str | None = None,
    *,
    record_usage: bool = False,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    ttl_ms = max(0, int(self.config.get_int("API.OPENAI.KEY_QUOTAS.RESERVATION_TTL_SEC")) * 1000)
    ip_value = str(client_ip or "").strip()
    resolved_ip = ip_value or None
    try:
        if resolved_ip is not None or record_usage:
            return await self.core.writer.queue_write_operation(
                sync_reserve_quota_units_for_mode_with_usage,
                key_id,
                expected_mode,
                int(estimate_units),
                int(now_ts),
                int(ttl_ms),
                resolved_ip,
            )
        return await self.core.writer.queue_write_operation(
            sync_reserve_quota_units_for_mode,
            key_id,
            expected_mode,
            int(estimate_units),
            int(now_ts),
            int(ttl_ms),
        )
    except DatabaseError as exception:
        raise_database_cause_if_needed(exception)
