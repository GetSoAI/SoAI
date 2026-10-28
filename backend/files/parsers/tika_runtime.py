"""SoAI - Managed Apache Tika server lifecycle [backend/files/parsers/tika_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from io import RawIOBase

from tika import tika

from core.bootstrap.java_runtime import ensure_java_runtime_installed
from core.bootstrap.tika_runtime_assets import TIKA_EXPECTED_VERSION, TIKA_SERVER_CONFIG_NAME
from core.bootstrap.tika_server_jar import ensure_tika_server_jar_installed
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import ProcessGroupCleanupError, StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.filesystem.open_files import open_binary
from core.logging.protocols import StandardLogger
from core.meta.paths import join_data_abs
from core.platform.os import is_macos, is_posix
from core.process.termination import terminate_subprocess_gracefully
from core.runtime.loopback_listener_identity import (
    LoopbackListenerIdentity,
    resolve_verified_loopback_listener_identity,
)
from core.runtime.process_identity_termination import (
    terminate_process_matching_identity,
)
from core.system.async_command_streams import close_managed_process_pipes
from core.system.async_process_spawning import (
    ManagedAsyncProcess,
    retain_managed_process_cleanup,
    spawn_async_process,
    spawn_managed_async_process,
    wait_for_async_process_exit,
)
from core.system.subprocess_env import build_minimal_subprocess_env
from core.system.subprocess_platform import windows_no_window_creationflags
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from files.parsers.tika_server_probe import (
    probe_tika_server_version,
    tika_server_is_ready,
    tika_startup_allowance,
    wait_until_tika_server_ready,
)

__all__ = ("TikaRuntime", "TikaRuntimeDependencies")

TIKA_ENDPOINT = "http://127.0.0.1:9997"
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
        self._process: asyncio.subprocess.Process | ManagedAsyncProcess | None = None
        self._identity: LoopbackListenerIdentity | None = None
        self._owns_identity = False
        self._log_handle: RawIOBase | None = None

    @property
    def endpoint(self) -> str:
        return TIKA_ENDPOINT

    async def start(self) -> None:
        async with self._lock:
            if await tika_server_is_ready(
                self._identity,
                self._process,
                host=_TIKA_HOST,
                port=_TIKA_PORT,
                expected_version=TIKA_EXPECTED_VERSION,
            ):
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
        java_home, java_binary = await run_joined_thread_call(
            ensure_java_runtime_installed,
            self._repo_root_path,
            task_name="tika-java-bootstrap",
        )
        jar_path, _jar_digest = await run_joined_thread_call(
            ensure_tika_server_jar_installed,
            self._repo_root_path,
            task_name="tika-distribution-bootstrap",
        )
        expected_parts = self._expected_command_parts(java_binary, jar_path)
        if not is_macos() and await self._attach_or_remove_verified_listener(expected_parts):
            self._configure_tika_client()
            return
        startup_allowance = await asyncio.to_thread(tika_startup_allowance, java_binary)
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
            "--config",
            os.path.join(os.path.dirname(os.path.dirname(jar_path)), TIKA_SERVER_CONFIG_NAME),
            "--host",
            _TIKA_HOST,
            "--port",
            str(_TIKA_PORT),
        ]
        environment = build_minimal_subprocess_env(
            {
                "JAVA_HOME": java_home,
                "PATH": os.pathsep.join((os.path.dirname(java_binary), os.environ.get("PATH", ""))),
            },
        )
        process: asyncio.subprocess.Process | ManagedAsyncProcess
        try:
            if is_posix():
                process = await spawn_managed_async_process(
                    argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=log_handle,
                    env=environment,
                    cwd=self._repo_root_path,
                    creationflags=windows_no_window_creationflags(),
                )
            else:
                process = await spawn_async_process(
                    argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=log_handle,
                    env=environment,
                    cwd=self._repo_root_path,
                    start_new_session=False,
                    creationflags=windows_no_window_creationflags(),
                )
            self._process = process
            self._owns_identity = True
            self._log_handle = log_handle
            self._identity = await wait_until_tika_server_ready(
                process,
                expected_parts,
                host=_TIKA_HOST,
                port=_TIKA_PORT,
                expected_version=TIKA_EXPECTED_VERSION,
                startup_allowance=startup_allowance,
            )
            self._configure_tika_client()
        except ProcessGroupCleanupError as exception:
            self._process = retain_managed_process_cleanup(exception)
            self._log_handle = log_handle
            self._owns_identity = True
            raise
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
        if (
            await probe_tika_server_version(host=_TIKA_HOST, port=_TIKA_PORT)
            == TIKA_EXPECTED_VERSION
        ):
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
        if isinstance(process, ManagedAsyncProcess):
            if process.process.returncode is None:
                await terminate_subprocess_gracefully(
                    process.process,
                    graceful_timeout_sec=RESPONSIVE_TIMEOUT_SEC,
                    logger=self._logger,
                    operation="files.parsers.tika_runtime.shutdown",
                    process_group=True,
                )
            await close_managed_process_pipes(
                process.process,
                process.connections,
                stdin_writer=process.stdin_writer,
            )
        elif identity is not None and owns_identity:
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
                process_group=False,
            )
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
            "--config",
            os.path.join(os.path.dirname(os.path.dirname(jar_path)), TIKA_SERVER_CONFIG_NAME),
            _TIKA_HOST,
            str(_TIKA_PORT),
        )


def _open_tika_log(path: str) -> RawIOBase:
    return open_binary(path, mode="ab", buffering=0)


def _close_tika_log(handle: RawIOBase) -> None:
    handle.close()
