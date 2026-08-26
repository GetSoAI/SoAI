"""SoAI - Plugin SDK disk reservation claim contexts [backend/plugin_sdk/contracts/disk_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)

if TYPE_CHECKING:
    from plugin_sdk.protocols import (
        ReservedWriteDiskReservationLeaseProtocol,
        ReservedWriteDiskWriteClaimProtocol,
    )

__all__ = ("claim_plugin_reserved_write",)


@asynccontextmanager
async def claim_plugin_reserved_write(
    reservation: ReservedWriteDiskReservationLeaseProtocol,
    *,
    size_bytes: int,
    cleanup_action: str,
) -> AsyncGenerator[None, None]:
    if size_bytes <= 0:
        yield
        return
    async with await reservation.claim_write_bytes(size_bytes) as claim:
        try:
            yield
        except asyncio.CancelledError as cancellation_exception:
            await _commit_claim_after_failure(
                claim,
                cancellation_exception,
                cleanup_action=cleanup_action,
            )
            raise
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as write_exception:
            await _commit_claim_after_failure(
                claim,
                write_exception,
                cleanup_action=cleanup_action,
            )
            raise
        await claim.commit()


async def _commit_claim_after_failure(
    claim: ReservedWriteDiskWriteClaimProtocol,
    primary_exception: BaseException,
    *,
    cleanup_action: str,
) -> None:
    try:
        await claim.commit()
    except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
        preserve_primary_exception_cleanup_failure(
            primary_exception,
            commit_exception,
            cleanup_action=cleanup_action,
        )
