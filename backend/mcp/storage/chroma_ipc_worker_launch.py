"""SoAI - Chroma IPC worker launch construction [backend/mcp/storage/chroma_ipc_worker_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError
from core.ipc.managed_worker import ManagedIpcWorkerDependencies
from core.ipc.settings import IPC_MAX_MESSAGE_BYTES_ENV_KEY
from core.meta.paths import get_repo_root, join_data_abs
from core.system.subprocess_env import build_minimal_subprocess_env

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.ipc.protocols import ManagedIpcWorkerProtocol
    from core.ipc.server import LocalIpcServer

__all__ = ("build_chroma_shard_worker",)


def build_chroma_shard_worker(
    *,
    shard_id: int,
    persist_dir: str,
    server: LocalIpcServer,
    managed_ipc_worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol],
) -> ManagedIpcWorkerProtocol:
    repo_root = get_repo_root()
    backend_dir = os.path.join(repo_root, "backend")
    log_dir = join_data_abs(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"chroma_worker_shard_{int(shard_id)}.log")
    diagnostic_log_path = os.path.join(
        log_dir,
        f"chroma_worker_shard_{int(shard_id)}.boot.log",
    )
    env_overrides: dict[str, str] = {
        "SOAI_IPC_HOST": server.host,
        "SOAI_IPC_PORT": str(server.port),
        "SOAI_IPC_TOKEN": server.token,
        "SOAI_IPC_WORKER_ID": str(int(shard_id)),
        IPC_MAX_MESSAGE_BYTES_ENV_KEY: str(server.max_message_bytes),
        "SOAI_CHROMA_PERSIST_DIR": str(persist_dir),
        "SOAI_CHROMA_WORKER_LOG": str(log_path),
    }
    python_executable = os.path.realpath(sys.executable)
    if not python_executable or not os.path.isfile(python_executable):
        raise ConfigurationError(
            "Invalid python executable for Chroma worker.",
            operation="mcp.storage.chroma_ipc.worker.python",
            details={"python_executable": python_executable},
        )
    deps = ManagedIpcWorkerDependencies(
        worker_id=int(shard_id),
        argv=[python_executable, "-m", "mcp.storage.chroma_ipc_worker"],
        cwd=backend_dir,
        diagnostic_log_path=diagnostic_log_path,
        env=build_minimal_subprocess_env(env_overrides),
    )
    return managed_ipc_worker_builder(deps)
