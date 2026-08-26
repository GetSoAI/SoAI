"""SoAI - Managed serialized video frame OCR IPC gateway [backend/core/media/ocr_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
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
from core.media.types import OcrFrameText
from core.meta.paths import get_repo_root
from core.system.subprocess_env import build_minimal_subprocess_env

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("OcrGateway", "OcrGatewayDependencies")

_WORKER_ID = 2
_OPERATION = "core.media.ocr_gateway"


@dataclass(frozen=True, slots=True)
class OcrGatewayDependencies:
    config: ConfigProtocol
    worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OcrGatewayDependencies",
            config=self.config,
            worker_builder=self.worker_builder,
        )


class OcrGateway:
    def __init__(self, deps: OcrGatewayDependencies) -> None:
        self._worker_builder = deps.worker_builder
        self._server, self._lifecycle = build_media_ipc_gateway(deps.config, _OPERATION)
        self._request_lock = asyncio.Lock()

    async def read_frame(
        self,
        *,
        frame_path: str,
        timestamp_seconds: float,
        timeout_seconds: float,
    ) -> OcrFrameText:
        async with self._request_lock:
            await self._ensure_started()
            try:
                response = await self._server.request(
                    _WORKER_ID,
                    method="read_frame",
                    request_id=secrets.token_hex(16),
                    payload={"frame_path": frame_path},
                    timeout_sec=timeout_seconds,
                )
            except asyncio.CancelledError as exception:
                await cleanup_failed_media_gateway_request(self._reset_worker(), exception)
                raise
            except TimeoutError as exception:
                timeout_error = SoAITimeoutError("Video frame OCR timed out.", cause=exception)
                await cleanup_failed_media_gateway_request(self._reset_worker(), timeout_error)
                raise timeout_error from exception
            except ServiceUnavailableError as exception:
                await raise_after_media_gateway_request_failure(
                    self._reset_worker(),
                    exception,
                    timeout_message="Video frame OCR timed out.",
                )
        payload = response.get("payload")
        if response.get("ok") is not True or not isinstance(payload, dict):
            raise ServiceUnavailableError("Video frame OCR failed.")
        text = payload.get("text")
        confidence = payload.get("confidence")
        if (
            not isinstance(text, str)
            or isinstance(confidence, bool)
            or not isinstance(confidence, int | float)
            or not math.isfinite(float(confidence))
        ):
            raise StateError("Video frame OCR returned an invalid payload.")
        return OcrFrameText(timestamp_seconds, " ".join(text.split()), float(confidence))

    async def shutdown(self) -> None:
        await self._reset_worker()

    async def _reset_worker(self) -> None:
        await self._lifecycle.reset()

    async def _ensure_started(self) -> None:
        await self._lifecycle.ensure_started(self._build_worker)

    def _build_worker(self) -> ManagedIpcWorkerProtocol:
        executable = str(sys.executable or "").strip()
        if not executable:
            raise ValidationError("Python executable is required for video OCR.")
        environment = {
            "SOAI_IPC_HOST": self._server.host,
            "SOAI_IPC_PORT": str(self._server.port),
            "SOAI_IPC_TOKEN": self._server.token,
            "SOAI_IPC_WORKER_ID": str(_WORKER_ID),
            IPC_MAX_MESSAGE_BYTES_ENV_KEY: str(self._server.max_message_bytes),
            "PATH": os.environ.get("PATH", ""),
            "SOAI_TESSERACT_CMD": os.environ.get("SOAI_TESSERACT_CMD", ""),
            "TESSDATA_PREFIX": os.environ.get("TESSDATA_PREFIX", ""),
        }
        return self._worker_builder(
            ManagedIpcWorkerDependencies(
                worker_id=_WORKER_ID,
                argv=[executable, "-m", "core.media.ocr_worker"],
                cwd=os.path.join(get_repo_root(), "backend"),
                env=build_minimal_subprocess_env(environment),
            ),
        )
