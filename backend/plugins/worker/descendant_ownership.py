"""SoAI - Worker descendant process ownership [backend/plugins/worker/descendant_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.runtime.process_descendants import (
    PROCESS_OBSERVATION_FAILURES,
    list_process_descendants_batch,
)
from core.runtime.process_identity_signals import (
    process_identity_matches,
    read_process_create_time_ms,
)

if TYPE_CHECKING:
    from core.runtime.backend_process_tracking import BackendProcessIdentity


__all__ = (
    "WorkerDescendantCapture",
    "WorkerDescendantRequest",
    "capture_worker_descendants_batch",
)


@dataclass(frozen=True, slots=True)
class WorkerDescendantRequest:
    worker_pid: int
    expected_create_time_ms: int | None
    retained: tuple[BackendProcessIdentity, ...]


@dataclass(frozen=True, slots=True)
class WorkerDescendantCapture:
    expected_create_time_ms: int | None
    identities: tuple[BackendProcessIdentity, ...]
    failure: psutil.Error | OSError | None = None


@dataclass(frozen=True, slots=True)
class _VerifiedWorkerProcess:
    index: int
    process: psutil.Process
    expected_create_time_ms: int
    identities: dict[tuple[int, int], BackendProcessIdentity]


def capture_worker_descendants_batch(
    requests: Sequence[WorkerDescendantRequest],
) -> list[WorkerDescendantCapture]:
    captures: dict[int, WorkerDescendantCapture] = {}
    verified: list[_VerifiedWorkerProcess] = []
    for index, request in enumerate(requests):
        try:
            identities = _revalidate_retained(request.retained)
        except PROCESS_OBSERVATION_FAILURES as exception:
            captures[index] = _failed(request, exception)
            continue
        try:
            worker = psutil.Process(request.worker_pid)
            current_create_time_ms = read_process_create_time_ms(worker)
        except psutil.NoSuchProcess:
            captures[index] = _settled(request.expected_create_time_ms, identities)
            continue
        except PROCESS_OBSERVATION_FAILURES as exception:
            captures[index] = _failed(request, exception)
            continue
        expected_create_time_ms = (
            current_create_time_ms
            if request.expected_create_time_ms is None
            else request.expected_create_time_ms
        )
        if current_create_time_ms != expected_create_time_ms:
            captures[index] = _settled(expected_create_time_ms, identities)
            continue
        verified.append(_VerifiedWorkerProcess(index, worker, expected_create_time_ms, identities))
    observations = list_process_descendants_batch([entry.process for entry in verified])
    for entry in verified:
        observation = observations[entry.process.pid]
        if isinstance(observation, psutil.NoSuchProcess):
            captures[entry.index] = _settled(entry.expected_create_time_ms, entry.identities)
            continue
        if not isinstance(observation, list):
            captures[entry.index] = _failed(requests[entry.index], observation)
            continue
        for child, created in observation:
            entry.identities[(child.pid, created)] = {"pid": child.pid, "createTimeMs": created}
        captures[entry.index] = _settled(entry.expected_create_time_ms, entry.identities)
    return [captures[index] for index in range(len(requests))]


def _revalidate_retained(
    retained: Sequence[BackendProcessIdentity],
) -> dict[tuple[int, int], BackendProcessIdentity]:
    identities: dict[tuple[int, int], BackendProcessIdentity] = {}
    for identity in retained:
        try:
            process = psutil.Process(identity["pid"])
            if process_identity_matches(process, identity["createTimeMs"]):
                identities[(identity["pid"], identity["createTimeMs"])] = identity
        except psutil.NoSuchProcess:
            continue
    return identities


def _settled(
    expected_create_time_ms: int | None,
    identities: dict[tuple[int, int], BackendProcessIdentity],
) -> WorkerDescendantCapture:
    return WorkerDescendantCapture(expected_create_time_ms, tuple(identities.values()))


def _failed(
    request: WorkerDescendantRequest,
    failure: psutil.Error | OSError,
) -> WorkerDescendantCapture:
    return WorkerDescendantCapture(request.expected_create_time_ms, request.retained, failure)
