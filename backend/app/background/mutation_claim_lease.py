"""SoAI - Durable mutation claim lease maintenance [backend/app/background/mutation_claim_lease.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.database.mutation_requests import MutationClaim
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.timing.epoch import epoch_ms

__all__ = ("maintain_mutation_claim_lease",)


async def maintain_mutation_claim_lease(
    database_tasks: DatabaseTasksProtocol,
    claim: MutationClaim,
    *,
    worker_id: str,
    lease_duration_ms: int,
    heartbeat_interval_sec: float,
    stopping_event: asyncio.Event,
    claim_lost_event: asyncio.Event,
) -> None:
    try:
        while not stopping_event.is_set():
            await asyncio.sleep(heartbeat_interval_sec)
            if stopping_event.is_set():
                return
            renewed = await database_tasks.renew_mutation_claim(
                claim.request_id,
                claim.fencing_token,
                worker_id,
                now_ms=epoch_ms(),
                lease_duration_ms=lease_duration_ms,
            )
            if renewed:
                continue
            claim_lost_event.set()
            return
    finally:
        if not stopping_event.is_set() and not claim_lost_event.is_set():
            claim_lost_event.set()
