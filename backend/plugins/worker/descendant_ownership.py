"""SoAI - Worker descendant process ownership [backend/plugins/worker/descendant_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import psutil

from core.runtime.process_identity_signals import (
    process_identity_matches,
    read_process_create_time_ms,
)

if TYPE_CHECKING:
    from core.runtime.backend_process_tracking import BackendProcessIdentity


__all__ = ("capture_worker_descendants",)


def capture_worker_descendants(
    worker_pid: int,
    expected_create_time_ms: int | None,
    retained: list[BackendProcessIdentity],
) -> tuple[int | None, list[BackendProcessIdentity]]:
    identities: dict[tuple[int, int], BackendProcessIdentity] = {}
    for identity in retained:
        try:
            process = psutil.Process(identity["pid"])
            if process_identity_matches(process, identity["createTimeMs"]):
                identities[(identity["pid"], identity["createTimeMs"])] = identity
        except psutil.NoSuchProcess:
            continue
    try:
        worker = psutil.Process(worker_pid)
        current_create_time_ms = read_process_create_time_ms(worker)
        if expected_create_time_ms is None:
            expected_create_time_ms = current_create_time_ms
        if current_create_time_ms != expected_create_time_ms:
            return expected_create_time_ms, list(identities.values())
        children = worker.children(recursive=True)
    except psutil.NoSuchProcess:
        return expected_create_time_ms, list(identities.values())
    for child in children:
        try:
            created = read_process_create_time_ms(child)
        except psutil.NoSuchProcess:
            continue
        identities[(child.pid, created)] = {"pid": child.pid, "createTimeMs": created}
    return expected_create_time_ms, list(identities.values())
