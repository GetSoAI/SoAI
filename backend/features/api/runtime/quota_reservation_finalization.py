"""SoAI - API quota reservation finalization [backend/features/api/runtime/quota_reservation_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.logging.trace import get_logger
from core.quotas.api_key_quota_reservation_finalization import (
    finalize_quota_reservation_required,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "finalize_quota_reservation_required_for_api",
    "release_quota_reservation_required",
)

LOGGER_NAME = "SoAI.features.api.quota_reservation_finalization"


async def finalize_quota_reservation_required_for_api(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    key_id: str,
    reservation: JSONDict,
    actual_units: int,
    trace_id: str | None,
    operation: str,
) -> None:
    await finalize_quota_reservation_required(
        database_api_keys=database_api_keys,
        key_id=key_id,
        reservation=reservation,
        actual_units=actual_units,
        logger=get_logger(LOGGER_NAME),
        trace_id=trace_id,
        operation=operation,
    )


async def release_quota_reservation_required(
    *,
    database_api_keys: DatabaseAPIKeysProtocol,
    key_id: str,
    reservation: JSONDict,
    trace_id: str | None,
    operation: str,
) -> None:
    await finalize_quota_reservation_required_for_api(
        database_api_keys=database_api_keys,
        key_id=key_id,
        reservation=reservation,
        actual_units=0,
        trace_id=trace_id,
        operation=operation,
    )
