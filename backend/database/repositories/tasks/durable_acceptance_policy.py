"""SoAI - Durable inference acceptance policy resolution [backend/database/repositories/tasks/durable_acceptance_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol

__all__ = (
    "DurableAcceptancePolicy",
    "build_durable_acceptance_policy",
)


@dataclass(frozen=True, slots=True)
class DurableAcceptancePolicy:
    durable_queue_hard_limit_tasks: int
    min_free_disk_bytes_for_accept: int
    acceptance_db_busy_timeout_sec: float
    filesystem_path: str


def build_durable_acceptance_policy(
    config: ConfigProtocol,
    *,
    database_path: str,
) -> DurableAcceptancePolicy:
    return DurableAcceptancePolicy(
        durable_queue_hard_limit_tasks=max(
            0,
            int(config.get_int("MODELS.ROUTING.DURABLE_QUEUE_HARD_LIMIT_TASKS")),
        ),
        min_free_disk_bytes_for_accept=max(
            0,
            int(config.get_int("MODELS.ROUTING.MIN_FREE_DISK_BYTES_FOR_ACCEPT")),
        ),
        acceptance_db_busy_timeout_sec=max(
            0.0,
            float(config.get_float("MODELS.ROUTING.ACCEPTANCE_DB_BUSY_TIMEOUT_SEC")),
        ),
        filesystem_path=_resolve_durable_acceptance_filesystem_path(
            config=config,
            database_path=database_path,
        ),
    )


def _resolve_durable_acceptance_filesystem_path(
    *,
    config: ConfigProtocol,
    database_path: str,
) -> str:
    for candidate in (
        database_path,
        config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB"),
        config.get_str("SYSTEM.PATHS.SYSTEM_DATA"),
    ):
        normalized = _normalize_path_candidate(candidate)
        if normalized is None:
            continue
        return os.path.abspath(_resolve_existing_filesystem_root(normalized))
    return os.path.abspath(".")


def _normalize_path_candidate(candidate: str | None) -> str | None:
    if not isinstance(candidate, str):
        return None
    normalized = candidate.strip()
    if not normalized or normalized == ":memory:" or normalized.startswith("file:"):
        return None
    return normalized


def _resolve_existing_filesystem_root(candidate: str) -> str:
    if os.path.isdir(candidate):
        return candidate
    directory = os.path.dirname(candidate)
    if directory:
        return directory
    return "."
