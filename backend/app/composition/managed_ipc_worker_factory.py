"""SoAI - Managed IPC worker factory for composition roots [backend/app/composition/managed_ipc_worker_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

from core.ipc.managed_worker import ManagedIpcWorker, ManagedIpcWorkerDependencies
from core.ipc.protocols import (
    ManagedIpcWorkerDependenciesProtocol,
    ManagedIpcWorkerFactoryProtocol,
    ManagedIpcWorkerProtocol,
)

__all__ = ("ManagedIpcWorkerFactory",)


class ManagedIpcWorkerFactory(ManagedIpcWorkerFactoryProtocol):
    @override
    def create(self, deps: ManagedIpcWorkerDependenciesProtocol) -> ManagedIpcWorkerProtocol:
        return ManagedIpcWorker(
            ManagedIpcWorkerDependencies(
                worker_id=int(deps.worker_id),
                argv=tuple(str(part) for part in deps.argv),
                cwd=str(deps.cwd),
                diagnostic_log_path=str(deps.diagnostic_log_path),
                env=dict(deps.env),
            ),
        )
