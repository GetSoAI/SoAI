"""SoAI - Plugin worker bootstrap helpers [backend/plugins/worker/worker_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ValidationError
from core.ipc.multiplexed import MultiplexedIpcServer
from core.ipc.settings import IPC_MAX_MESSAGE_BYTES_ENV_KEY
from core.meta.paths import get_backend_root
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object
from plugins.worker.surface import PluginRuntimeSurface

__all__ = (
    "build_plugin_worker_env",
    "load_plugin_worker_surface",
)


def _build_worker_python_path(*, backend_root: str, previous_python_path: str) -> str:
    backend_root_value = os.path.abspath(backend_root)
    repository_root = os.path.dirname(backend_root_value)
    path_entries: list[str] = [backend_root_value]
    for path_entry in previous_python_path.split(os.pathsep):
        normalized_entry = path_entry.strip()
        if not normalized_entry:
            continue
        absolute_entry = os.path.abspath(normalized_entry)
        if absolute_entry in {backend_root_value, repository_root}:
            continue
        path_entries.append(normalized_entry)
    return os.pathsep.join(path_entries)


def build_plugin_worker_env(
    *,
    server: MultiplexedIpcServer,
    worker_id: int,
    worker_secret: str,
    bootstrap: JSONDict,
) -> dict[str, str]:
    env = dict(os.environ)
    backend_root = get_backend_root()
    previous_python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _build_worker_python_path(
        backend_root=backend_root,
        previous_python_path=previous_python_path,
    )
    env["SOAI_IPC_HOST"] = server.host
    env["SOAI_IPC_PORT"] = str(server.port)
    env["SOAI_IPC_TOKEN"] = server.token
    env["SOAI_IPC_WORKER_ID"] = str(worker_id)
    env["SOAI_IPC_WORKER_SECRET"] = str(worker_secret)
    env[IPC_MAX_MESSAGE_BYTES_ENV_KEY] = str(server.max_message_bytes)
    env["SOAI_PLUGIN_WORKER_BOOTSTRAP"] = serialize_json_compact_stable_strict(
        bootstrap,
        ensure_ascii=True,
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


async def load_plugin_worker_surface(
    *,
    server: MultiplexedIpcServer,
    worker_id: int,
    surface_timeout_sec: float,
) -> PluginRuntimeSurface:
    response = await server.request(
        worker_id,
        method="bootstrap.surface",
        request_id=f"plugin_surface_{worker_id}",
        payload={},
        timeout_sec=surface_timeout_sec,
    )
    payload_value = response.get("payload")
    payload = require_json_object(
        payload_value,
        label="Plugin worker surface response payload",
        build_error=ValidationError,
        invalid_message="Plugin worker surface response payload must be a JSON object.",
    )
    return PluginRuntimeSurface.from_payload(payload)
