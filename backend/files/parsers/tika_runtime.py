"""SoAI - Managed Apache Tika server lifecycle [backend/files/parsers/tika_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from io import RawIOBase

import psutil
from tika import tika

from core.bootstrap.java_runtime import ensure_java_runtime_installed
from core.bootstrap.tika_server_jar import ensure_tika_server_jar_installed
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.filesystem.open_files import open_binary
from core.logging.protocols import StandardLogger
from core.meta.paths import join_data_abs
from core.platform.os import is_macos, is_posix
from core.process.termination import terminate_subprocess_gracefully
from core.runtime.loopback_listener_identity import (
    LoopbackListenerIdentity,
    resolve_verified_loopback_listener_identity,
    resolve_verified_loopback_listener_process_identity,
)
from core.runtime.process_identity_termination import (
    terminate_process_matching_identity,
)
from core.system.async_process_spawning import (
    spawn_async_process,
    wait_for_async_process_exit,
)
from core.system.subprocess_env import build_minimal_subprocess_env
from core.system.subprocess_platform import windows_no_window_creationflags
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC

__all__ = ("TikaRuntime", "TikaRuntimeDependencies")

TIKA_ENDPOINT = "http://127.0.0.1:9997"
TIKA_EXPECTED_VERSION = "Apache Tika 3.3.2"
_TIKA_HOST = "127.0.0.1"
_TIKA_PORT = 9997
_TIKA_MAIN_CLASS = "org.apache.tika.server.core.TikaServerCli"


@dataclass(frozen=True, slots=True)
class TikaRuntimeDependencies:
    repo_root_path: str
    logger: StandardLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TikaRuntimeDependencies",
            repo_root_path=self.repo_root_path,
            logger=self.logger,
        )
        if not self.repo_root_path.strip():
            raise StateError("Tika runtime repository root is required.")


class TikaRuntime:
    def __init__(self, deps: TikaRuntimeDependencies) -> None:
        self._repo_root_path = os.path.abspath(deps.repo_root_path)
        self._logger = deps.logger
        self._lock = asyncio.Lock()
        self._process: asyncio.subprocess.Process | None = None
        self._identity: LoopbackListenerIdentity | None = None
        self._owns_identity = False
        self._log_handle: RawIOBase | None = None

    @property
    def endpoint(self) -> str:
        return TIKA_ENDPOINT

    async def start(self) -> None:
        async with self._lock:
            if await self._server_is_ready():
                return
            await self._stop_locked()
            await self._start_locked()

    async def restart(self) -> None:
        async with self._lock:
            await self._stop_locked()
            await self._start_locked()

    async def shutdown(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _start_locked(self) -> None:
        java_home, java_binary = ensure_java_runtime_installed(self._repo_root_path)
        jar_path, _jar_digest = ensure_tika_server_jar_installed(self._repo_root_path)
        expected_parts = self._expected_command_parts(java_binary, jar_path)
        if not is_macos() and await self._attach_or_remove_verified_listener(expected_parts):
            self._configure_tika_client()
            return
        log_path = join_data_abs(self._repo_root_path, "state", "tika", "logs", "server.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_handle = await run_joined_thread_call(
            _open_tika_log,
            log_path,
            task_name="tika-log-open",
            cancelled_result_cleanup=_close_tika_log,
        )
        argv = [
            java_binary,
            "-Dpoi.minInflateRatio=0.0001",
            "-cp",
            jar_path,
            _TIKA_MAIN_CLASS,
            "--noFork",
            "--host",
            _TIKA_HOST,
            "--port",
            str(_TIKA_PORT),
        ]
        environment = build_minimal_subprocess_env(
            {
                "JAVA_HOME": java_home,
                "PATH": os.path.dirname(java_binary),
            },
        )
        try:
            process = await spawn_async_process(
                argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=log_handle,
                stderr=log_handle,
                env=environment,
                cwd=self._repo_root_path,
                start_new_session=is_posix(),
                creationflags=windows_no_window_creationflags(),
            )
            self._process = process
            self._owns_identity = True
            self._log_handle = log_handle
            await self._wait_until_ready(process, expected_parts)
            self._configure_tika_client()
        except asyncio.CancelledError:
            if self._log_handle is None:
                log_handle.close()
            await uncancel_then_cleanup(self._stop_locked())
            raise
        except HANDLED_RUNTIME_EXCEPTIONS:
            if self._log_handle is None:
                log_handle.close()
            await uncancel_then_cleanup(self._stop_locked())
            raise

    async def _wait_until_ready(
        self,
        process: asyncio.subprocess.Process,
        expected_parts: tuple[str, ...],
    ) -> None:
        deadline = time.monotonic() + LONG_REQUEST_TIMEOUT_SEC
        while time.monotonic() < deadline:
            if process.returncode is not None:
                raise StateError(
                    f"Managed Apache Tika server exited with code {process.returncode}.",
                )
            version = await self._probe_version()
            if version == TIKA_EXPECTED_VERSION:
                resolution = resolve_verified_loopback_listener_process_identity(
                    pid=process.pid,
                    host=_TIKA_HOST,
                    port=_TIKA_PORT,
                    expected_command_parts=expected_parts,
                )
                if resolution.ownership_verified and resolution.identity is not None:
                    self._identity = resolution.identity
                    return
                if resolution.listener_found:
                    raise StateError("Managed Apache Tika listener identity could not be verified.")
            if version:
                raise StateError(f"Unexpected Apache Tika server version: {version}")
            await asyncio.sleep(RESPONSIVE_TIMEOUT_SEC)
        raise TimeoutError("Managed Apache Tika server startup timed out.")

    async def _probe_version(self) -> str:
        try:
            return await run_joined_thread_call(
                _read_tika_version,
                task_name="tika-version-probe",
            )
        except (HTTPException, OSError):
            return ""

    async def _server_is_ready(self) -> bool:
        identity = self._identity
        process = self._process
        if identity is None or (process is not None and process.returncode is not None):
            return False
        try:
            current = psutil.Process(identity.pid)
            create_time_ms = int(current.create_time() * 1000.0)
        except (psutil.Error, OSError):
            return False
        if create_time_ms != identity.create_time_ms:
            return False
        return await self._probe_version() == TIKA_EXPECTED_VERSION

    async def _attach_or_remove_verified_listener(
        self,
        expected_parts: tuple[str, ...],
    ) -> bool:
        resolution = resolve_verified_loopback_listener_identity(
            host=_TIKA_HOST,
            port=_TIKA_PORT,
            expected_command_parts=expected_parts,
            logger=self._logger,
        )
        if not resolution.listener_found:
            return False
        if not resolution.ownership_verified or resolution.identity is None:
            raise StateError(f"Port {_TIKA_PORT} is occupied by an unverified listener.")
        if await self._probe_version() == TIKA_EXPECTED_VERSION:
            self._identity = resolution.identity
            self._owns_identity = True
            return True
        terminated = await terminate_process_matching_identity(
            resolution.identity.pid,
            resolution.identity.create_time_ms,
            "managed Apache Tika server",
            self._logger,
            graceful_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
            force_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
        )
        if not terminated.terminated:
            raise StateError("Failed to terminate the verified stale Apache Tika server.")
        return False

    async def _stop_locked(self) -> None:
        identity = self._identity
        process = self._process
        owns_identity = self._owns_identity
        try:
            if identity is not None and owns_identity:
                terminated = await terminate_process_matching_identity(
                    identity.pid,
                    identity.create_time_ms,
                    "managed Apache Tika server",
                    self._logger,
                    graceful_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                    force_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                )
                if not terminated.terminated:
                    raise StateError("Failed to terminate the managed Apache Tika server.")
                if process is not None:
                    await wait_for_async_process_exit(
                        process,
                        timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                        kill_on_timeout=True,
                    )
            elif process is not None and process.returncode is None:
                await terminate_subprocess_gracefully(
                    process,
                    graceful_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                    logger=self._logger,
                    operation="files.parsers.tika_runtime.shutdown",
                    process_group=is_posix(),
                )
        finally:
            self._close_log_handle()
        self._identity = None
        self._process = None
        self._owns_identity = False

    def _close_log_handle(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def _configure_tika_client(self) -> None:
        tika.TikaClientOnly = True
        tika.ServerEndpoint = TIKA_ENDPOINT
        self._logger.info("Managed Apache Tika server is ready on %s.", TIKA_ENDPOINT)

    @staticmethod
    def _expected_command_parts(java_binary: str, jar_path: str) -> tuple[str, ...]:
        return (
            java_binary,
            jar_path,
            _TIKA_MAIN_CLASS,
            "--noFork",
            _TIKA_HOST,
            str(_TIKA_PORT),
        )


def _read_tika_version() -> str:
    connection = HTTPConnection(
        _TIKA_HOST,
        _TIKA_PORT,
        timeout=RESPONSIVE_TIMEOUT_SEC,
    )
    try:
        connection.request("GET", "/version")
        response = connection.getresponse()
        if response.status != 200:
            return ""
        return response.read(256).decode("utf-8", errors="strict").strip()
    finally:
        connection.close()


def _open_tika_log(path: str) -> RawIOBase:
    return open_binary(path, mode="ab", buffering=0)


def _close_tika_log(handle: RawIOBase) -> None:
    handle.close()
