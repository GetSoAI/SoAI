"""SoAI - RAG conversation maintenance lease lifecycle [backend/mcp/rag/maintenance_locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.durations import seconds_to_ms
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.files.protocols import DatabaseFilesProtocol

__all__ = (
    "acquire_rag_maintenance_lease",
    "release_rag_maintenance_lease",
    "renew_rag_maintenance_lease",
)

_DEFAULT_MAINTENANCE_LEASE_TTL_SECONDS = 900


def _lease_expires_at_ms(config: ConfigProtocol) -> int:
    ttl_seconds = config.get_int("TOOLS.RAG.PROCESSING_JOB_LEASE_TTL_SEC")
    ttl_seconds = max(ttl_seconds, _DEFAULT_MAINTENANCE_LEASE_TTL_SECONDS)
    return int(epoch_ms()) + seconds_to_ms(ttl_seconds)


async def acquire_rag_maintenance_lease(
    *,
    database_files: DatabaseFilesProtocol,
    config: ConfigProtocol,
    conv_id: str,
    lock_type: str,
    owner_task_id: str,
    lease_owner: str,
    unavailable_message: str,
) -> str:
    lease_token = uuid.uuid4().hex
    acquired = await database_files.acquire_rag_maintenance_lock(
        conv_id=conv_id,
        lock_type=lock_type,
        owner_task_id=owner_task_id,
        lease_token=lease_token,
        lease_owner=lease_owner,
        lease_expires_at_ms=_lease_expires_at_ms(config),
        now_ms=int(epoch_ms()),
    )
    if not acquired:
        raise ValidationError(unavailable_message)
    return lease_token


async def release_rag_maintenance_lease(
    *,
    database_files: DatabaseFilesProtocol,
    conv_id: str,
    lease_token: str | None,
) -> None:
    if lease_token is None:
        return
    await database_files.release_rag_maintenance_lock(
        conv_id=conv_id,
        lease_token=lease_token,
    )


async def renew_rag_maintenance_lease(
    *,
    database_files: DatabaseFilesProtocol,
    config: ConfigProtocol,
    conv_id: str,
    lease_token: str,
    expired_message: str,
) -> None:
    renewed = await database_files.renew_rag_maintenance_lock(
        conv_id=conv_id,
        lease_token=lease_token,
        lease_expires_at_ms=_lease_expires_at_ms(config),
        now_ms=int(epoch_ms()),
    )
    if not renewed:
        raise ValidationError(expired_message)
