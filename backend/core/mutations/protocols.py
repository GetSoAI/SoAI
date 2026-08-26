"""SoAI - Durable mutation contribution protocols [backend/core/mutations/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Sequence
from typing import Protocol

from cryptography.fernet import Fernet

from core.database.mutation_requests import (
    MutationAdmissionRequest,
    MutationClaim,
    MutationRecoveryCandidate,
)
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.events.types_base import Event, ReplyableCommand
from core.runtime.request_context import RequestContext

__all__ = (
    "MutationAdmissionHookProtocol",
    "MutationClaimProtocol",
    "MutationDecoderProtocol",
    "MutationRecoveryReleaseProtocol",
)


class MutationDecoderProtocol(Protocol):
    def __call__(
        self,
        claim: MutationClaim,
        *,
        context: RequestContext,
        reply_queue: asyncio.Queue[Event],
        fernets: Sequence[Fernet],
    ) -> ReplyableCommand | None: ...


class MutationClaimProtocol(Protocol):
    async def __call__(
        self,
        database_tasks: DatabaseTasksProtocol,
        candidate: MutationRecoveryCandidate,
        *,
        plugin_directory: str,
        worker_id: str,
        now_ms: int,
        lease_duration_ms: int,
    ) -> MutationClaim | None: ...


class MutationAdmissionHookProtocol(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        request: MutationAdmissionRequest,
        *,
        completed_at_ms: int,
    ) -> None: ...


class MutationRecoveryReleaseProtocol(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        request_id: str,
        target_identity: str,
        completed_at_ms: int,
    ) -> bool: ...
