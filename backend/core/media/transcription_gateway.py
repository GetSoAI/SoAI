"""SoAI - Managed serialized Whisper IPC gateway [backend/core/media/transcription_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import (
    ServiceUnavailableError,
    SoAITimeoutError,
    StateError,
    ValidationError,
)
from core.ipc.managed_worker import ManagedIpcWorkerDependencies
from core.ipc.protocols import ManagedIpcWorkerProtocol
from core.ipc.settings import IPC_MAX_MESSAGE_BYTES_ENV_KEY
from core.media.ipc_gateway_lifecycle import (
    build_media_ipc_gateway,
    cleanup_failed_media_gateway_request,
    raise_after_media_gateway_request_failure,
)
from core.meta.paths import get_repo_root
from core.runtime.network_policy import OfflineModeError
from core.system.subprocess_env import build_minimal_subprocess_env

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict

__all__ = ("TranscriptionGateway", "TranscriptionGatewayDependencies")

_WORKER_ID = 1
_OPERATION = "core.media.transcription_gateway"


@dataclass(frozen=True, slots=True)
class TranscriptionGatewayDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TranscriptionGatewayDependencies",
            config=self.config,
            runtime_flags=self.runtime_flags,
            worker_builder=self.worker_builder,
        )


class TranscriptionGateway:
    def __init__(self, deps: TranscriptionGatewayDependencies) -> None:
        self._runtime_flags = deps.runtime_flags
        self._worker_builder = deps.worker_builder
        self._server, self._lifecycle = build_media_ipc_gateway(deps.config, _OPERATION)
        self._transcription_lock = asyncio.Lock()

    async def transcribe_chunk(
        self,
        *,
        file_path: str,
        model_name: str,
        language: str | None,
        task: str,
        include_word_timestamps: bool,
        timeout_seconds: float,
    ) -> JSONDict:
        async with self._transcription_lock:
            await self._ensure_started()
            try:
                response = await self._server.request(
                    _WORKER_ID,
                    method="transcribe_chunk",
                    request_id=secrets.token_hex(16),
                    payload={
                        "file_path": file_path,
                        "model": model_name,
                        "language": language,
                        "task": task,
                        "include_word_timestamps": include_word_timestamps,
                        "offline_mode": bool(self._runtime_flags.offline_mode),
                    },
                    timeout_sec=timeout_seconds,
                )
            except asyncio.CancelledError as exception:
                await cleanup_failed_media_gateway_request(self._reset_worker(), exception)
                raise
            except TimeoutError as exception:
                timeout_error = SoAITimeoutError(
                    "Media transcription timed out.",
                    cause=exception,
                )
                await cleanup_failed_media_gateway_request(self._reset_worker(), timeout_error)
                raise timeout_error from exception
            except ServiceUnavailableError as exception:
                await raise_after_media_gateway_request_failure(
                    self._reset_worker(),
                    exception,
                    timeout_message="Media transcription timed out.",
                )
        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise StateError("Media transcription worker returned an invalid payload.")
        if response.get("ok") is True:
            return payload
        message = payload.get("message")
        safe_message = (
            message if isinstance(message, str) and message else "Media transcription failed."
        )
        if payload.get("error") == "offline_mode":
            raise OfflineModeError(safe_message)
        raise ServiceUnavailableError(safe_message)

    async def shutdown(self) -> None:
        await self._reset_worker()

    async def _reset_worker(self) -> None:
        await self._lifecycle.reset()

    async def _ensure_started(self) -> None:
        await self._lifecycle.ensure_started(self._build_worker)

    def _build_worker(self) -> ManagedIpcWorkerProtocol:
        executable = str(sys.executable or "").strip()
        if not executable:
            raise ValidationError("Python executable is required for media transcription.")
        backend_dir = os.path.join(get_repo_root(), "backend")
        overrides = {
            "SOAI_IPC_HOST": self._server.host,
            "SOAI_IPC_PORT": str(self._server.port),
            "SOAI_IPC_TOKEN": self._server.token,
            "SOAI_IPC_WORKER_ID": str(_WORKER_ID),
            IPC_MAX_MESSAGE_BYTES_ENV_KEY: str(self._server.max_message_bytes),
            "SOAI_STAY_OFFLINE": "1" if self._runtime_flags.offline_mode else "0",
            "PATH": _worker_path(executable),
        }
        return self._worker_builder(
            ManagedIpcWorkerDependencies(
                worker_id=_WORKER_ID,
                argv=[executable, "-m", "core.media.transcription_worker"],
                cwd=backend_dir,
                env=build_minimal_subprocess_env(overrides),
            ),
        )


def _worker_path(executable: str) -> str:
    binary_dir = os.path.dirname(executable)
    environment_dir = os.path.dirname(binary_dir)
    entries = [
        binary_dir,
        os.path.join(environment_dir, "Scripts"),
        os.path.join(environment_dir, "Library", "bin"),
        os.path.join(environment_dir, "Library", "usr", "bin"),
    ]
    inherited = os.environ.get("PATH", "")
    if inherited:
        entries.append(inherited)
    return os.pathsep.join(dict.fromkeys(entries))
