"""SoAI - Apache Tika version and verified listener readiness [backend/files/parsers/tika_server_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from functools import partial
from http.client import HTTPConnection, HTTPException

import psutil

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import StateError
from core.process.termination import poll_process_exit_without_reaping
from core.runtime.loopback_listener_identity import (
    LoopbackListenerIdentity,
    resolve_verified_loopback_listener_process_identity,
)
from core.system.async_process_spawning import ManagedAsyncProcess
from core.system.native_image_budget import NativeImageAllowance, native_image_allowance
from core.system.native_runtime_probes import RuntimeStartupTimeoutError, runtime_timeout_error
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC

__all__ = (
    "wait_until_tika_server_ready",
    "probe_tika_server_version",
    "tika_server_is_ready",
    "tika_startup_allowance",
)


async def wait_until_tika_server_ready(
    process: asyncio.subprocess.Process | ManagedAsyncProcess,
    expected_parts: tuple[str, ...],
    *,
    host: str,
    port: int,
    expected_version: str,
    startup_allowance: NativeImageAllowance,
) -> LoopbackListenerIdentity:
    deadline = time.monotonic() + startup_allowance.seconds
    child = process.process if isinstance(process, ManagedAsyncProcess) else process
    while time.monotonic() < deadline:
        return_code = (
            poll_process_exit_without_reaping(process.process)
            if isinstance(process, ManagedAsyncProcess)
            else process.returncode
        )
        if return_code is not None:
            raise StateError(
                f"Managed Apache Tika server exited with code {return_code}.",
            )
        version = await probe_tika_server_version(host=host, port=port)
        if version == expected_version:
            resolution = resolve_verified_loopback_listener_process_identity(
                pid=child.pid,
                host=host,
                port=port,
                expected_command_parts=expected_parts,
            )
            if resolution.ownership_verified and resolution.identity is not None:
                return resolution.identity
            if resolution.listener_found:
                raise StateError("Managed Apache Tika listener identity could not be verified.")
        if version:
            raise StateError(f"Unexpected Apache Tika server version: {version}")
        await asyncio.sleep(RESPONSIVE_TIMEOUT_SEC)
    raise runtime_timeout_error(
        RuntimeStartupTimeoutError,
        subject="The managed Apache Tika server startup",
        allowance=startup_allowance,
    )


def tika_startup_allowance(java_binary: str) -> NativeImageAllowance:
    return native_image_allowance(LONG_REQUEST_TIMEOUT_SEC, roots=(os.path.dirname(java_binary),))


async def probe_tika_server_version(*, host: str, port: int) -> str:
    try:
        return await run_joined_thread_call(
            partial(_read_tika_version, host, port),
            task_name="tika-version-probe",
        )
    except (HTTPException, OSError):
        return ""


async def tika_server_is_ready(
    identity: LoopbackListenerIdentity | None,
    process: asyncio.subprocess.Process | ManagedAsyncProcess | None,
    *,
    host: str,
    port: int,
    expected_version: str,
) -> bool:
    child = process.process if isinstance(process, ManagedAsyncProcess) else process
    if identity is None:
        return False
    return_code = (
        poll_process_exit_without_reaping(process.process)
        if isinstance(process, ManagedAsyncProcess)
        else child.returncode if child is not None else None
    )
    if return_code is not None:
        return False
    try:
        current = psutil.Process(identity.pid)
        create_time_ms = int(current.create_time() * 1000.0)
    except (psutil.Error, OSError):
        return False
    if create_time_ms != identity.create_time_ms:
        return False
    return await probe_tika_server_version(host=host, port=port) == expected_version


def _read_tika_version(host: str, port: int) -> str:
    connection = HTTPConnection(
        host,
        port,
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
