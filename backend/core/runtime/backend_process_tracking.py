"""SoAI - Backend process identity tracking and cleanup [backend/core/runtime/backend_process_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

import psutil

from core.runtime.process_identity_kill import force_kill_process_tree_matching_identity
from core.runtime.process_identity_signals import (
    read_process_create_time_ms,
    wait_for_process_identity_mismatch_or_gone,
)
from core.validation.integers import is_positive_strict_int, is_strict_int

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "BackendProcessCleanupResult",
    "BackendProcessIdentity",
    "backend_process_identities_match",
    "backend_process_identities_to_json_dicts",
    "backend_process_identity_to_json_dict",
    "cleanup_backend_process_identities",
    "normalize_backend_process_pids",
    "resolve_backend_process_identities",
)


class BackendProcessIdentity(TypedDict):
    pid: int
    createTimeMs: int


@dataclass(frozen=True, slots=True)
class BackendProcessCleanupResult:
    killed: list[BackendProcessIdentity]
    mismatched: list[BackendProcessIdentity]
    already_gone: list[BackendProcessIdentity]
    failed: list[BackendProcessIdentity]

    @property
    def succeeded(self) -> bool:
        return not self.failed


def _read_process_create_time_ms(pid: int) -> int | None:
    try:
        process = psutil.Process(pid)
        return read_process_create_time_ms(process)
    except psutil.NoSuchProcess:
        return None


def normalize_backend_process_pids(raw_pids: list[int]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for pid in raw_pids:
        if not is_strict_int(pid):
            continue
        if pid <= 0:
            continue
        if pid in seen:
            continue
        seen.add(pid)
        normalized.append(pid)
    return normalized


def backend_process_identity_to_json_dict(identity: BackendProcessIdentity) -> dict[str, int]:
    return {"pid": identity["pid"], "createTimeMs": identity["createTimeMs"]}


def backend_process_identities_to_json_dicts(
    identities: list[BackendProcessIdentity],
) -> list[dict[str, int]]:
    return [backend_process_identity_to_json_dict(identity) for identity in identities]


def backend_process_identities_match(
    left: list[BackendProcessIdentity],
    right: list[BackendProcessIdentity],
) -> bool:
    return _backend_process_identity_keys(left) == _backend_process_identity_keys(right)


def _backend_process_identity_keys(
    identities: list[BackendProcessIdentity],
) -> list[tuple[int, int]]:
    return sorted((identity["pid"], identity["createTimeMs"]) for identity in identities)


def resolve_backend_process_identities(
    pids: list[int],
    *,
    plugin_name: str,
    logger: LoggerProtocol,
) -> list[BackendProcessIdentity]:
    identities: list[BackendProcessIdentity] = []
    for pid in normalize_backend_process_pids(pids):
        try:
            create_time_ms = _read_process_create_time_ms(pid)
        except psutil.AccessDenied as exception:
            logger.error(
                "Cannot read create time for plugin '%s' PID %s: %s",
                plugin_name,
                pid,
                f"{type(exception).__name__}: {exception}",
            )
            raise
        if create_time_ms is None:
            continue
        identities.append({"pid": pid, "createTimeMs": create_time_ms})
    return identities


async def cleanup_backend_process_identities(
    identities: list[BackendProcessIdentity],
    *,
    plugin_name: str,
    logger: LoggerProtocol,
) -> BackendProcessCleanupResult:
    killed: list[BackendProcessIdentity] = []
    mismatched: list[BackendProcessIdentity] = []
    already_gone: list[BackendProcessIdentity] = []
    failed: list[BackendProcessIdentity] = []
    for identity in identities:
        pid_value = identity.get("pid")
        create_time_value = identity.get("createTimeMs")
        if not is_positive_strict_int(pid_value):
            logger.critical(
                "Invalid backend process identity for plugin '%s': %s",
                plugin_name,
                {"pid": pid_value, "createTimeMs": create_time_value},
            )
            failed.append(identity)
            continue
        if not is_positive_strict_int(create_time_value):
            logger.critical(
                "Invalid backend process identity for plugin '%s': %s",
                plugin_name,
                {"pid": pid_value, "createTimeMs": create_time_value},
            )
            failed.append(identity)
            continue
        try:
            current_create_time_ms = _read_process_create_time_ms(pid_value)
        except psutil.AccessDenied as exception:
            logger.critical(
                "Cannot verify backend process identity for plugin '%s' PID %s: %s",
                plugin_name,
                pid_value,
                f"{type(exception).__name__}: {exception}",
            )
            failed.append(identity)
            continue
        if current_create_time_ms is None:
            already_gone.append(identity)
            continue
        if current_create_time_ms != create_time_value:
            mismatched.append(identity)
            continue
        kill_result = await force_kill_process_tree_matching_identity(
            pid_value,
            create_time_value,
            plugin_name,
            logger,
        )
        if kill_result.process_not_found:
            already_gone.append(identity)
            continue
        if kill_result.identity_mismatched:
            mismatched.append(identity)
            continue
        if not kill_result.success:
            failed.append(identity)
            continue
        if not await wait_for_process_identity_mismatch_or_gone(
            pid_value,
            create_time_value,
            timeout_sec=1.0,
        ):
            logger.critical(
                "Backend process identity for plugin '%s' PID %s still matches after force-kill.",
                plugin_name,
                pid_value,
            )
            failed.append(identity)
            continue
        killed.append(identity)
    return BackendProcessCleanupResult(
        killed=killed,
        mismatched=mismatched,
        already_gone=already_gone,
        failed=failed,
    )
