"""SoAI - Owned native probe capture and termination [backend/plugin_sdk/contracts/native_runtime_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import re
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.backend_lifecycle import NativeProbeTerminationError
from core.platform.os import is_windows
from core.system.native_image_budget import NativeImageAllowance
from plugin_sdk.contracts.config_access import get_config_float
from plugin_sdk.contracts.process_sessions import spawn_logged_process, terminate_logged_process
from plugin_sdk.protocols import PluginSdkRuntimeAttributesProtocol

__all__ = ("NativeRuntimeProbeResult", "run_native_runtime_probe", "classify_llama_server_probe")


@dataclass(frozen=True, slots=True)
class NativeRuntimeProbeResult:
    stdout: str
    stderr: str
    return_code: int | None
    started: bool
    timed_out: bool
    elapsed_seconds: float
    allowance: NativeImageAllowance


def classify_llama_server_probe(
    result: NativeRuntimeProbeResult,
    *,
    artifact_tag: str,
    binary_present: bool,
    expected_version: str | None = None,
    expected_commit: str | None = None,
) -> tuple[str, str | None]:
    matched = re.search(
        r"version:\s+(\S+)\s+\(build (\d+), commit ([0-9a-f]+)\)",
        f"{result.stdout}\n{result.stderr}",
    )
    if result.timed_out:
        return "timeout", None
    if not binary_present and (not result.started or result.return_code == 127):
        return "missing_executable", None
    if not result.started:
        return "start_failed", None
    if result.return_code != 0:
        return "nonzero_exit", None
    if matched is None:
        return "malformed_version", None
    version, build, commit = matched.groups()
    if re.fullmatch(r"b\d+", artifact_tag) is not None and build != artifact_tag.removeprefix("b"):
        return "wrong_build_identity", None
    if expected_version is not None and version != expected_version:
        return "wrong_build_identity", None
    if expected_commit is not None and (len(commit) < 8 or not expected_commit.startswith(commit)):
        return "wrong_build_identity", None
    return "verified", version


def _open_captures(directory: str) -> tuple[io.BufferedIOBase, io.BufferedIOBase]:
    stdout = tempfile.TemporaryFile(prefix="native-probe-", dir=directory)
    try:
        return stdout, tempfile.TemporaryFile(prefix="native-probe-", dir=directory)
    except OSError:
        stdout.close()
        raise


def _close_captures(captures: tuple[io.BufferedIOBase, io.BufferedIOBase]) -> None:
    try:
        captures[0].close()
    finally:
        captures[1].close()


def _read_capture(capture: io.BufferedIOBase) -> str:
    capture.seek(0)
    return capture.read().decode("utf-8", errors="replace")


async def run_native_runtime_probe(
    plugin: PluginSdkRuntimeAttributesProtocol,
    argv: Sequence[str],
    *,
    allowance: NativeImageAllowance,
    environment: Mapping[str, str],
    cwd: str | None,
    plugin_label: str = "native-runtime-probe",
) -> NativeRuntimeProbeResult:
    captures = await run_joined_thread_call(
        _open_captures,
        plugin.temp_directory,
        task_name="native-probe.open-capture",
        retain_resources_until_complete=True,
        cancelled_result_cleanup=_close_captures,
    )
    started = time.monotonic()
    try:
        try:
            session = await spawn_logged_process(
                argv,
                cwd=cwd,
                env=environment,
                logger=plugin.logger,
                plugin_label=plugin_label,
                log_file_handle=None,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=captures[0].fileno(),
                stderr=captures[1].fileno(),
                start_new_session=not is_windows(),
            )
        except OSError as exception:
            result = NativeRuntimeProbeResult(
                "",
                f"Command could not start: {exception!s}",
                None,
                False,
                False,
                time.monotonic() - started,
                allowance,
            )
        else:
            timed_out = False
            try:
                await asyncio.wait_for(session.process.wait(), timeout=allowance.seconds)
            except TimeoutError:
                timed_out = True
            finally:
                if session.process.returncode is None:
                    terminated = await uncancel_then_cleanup(
                        terminate_logged_process(
                            session,
                            logger=plugin.logger,
                            plugin_label=plugin_label,
                            shutdown_timeout_sec=0.0,
                            kill_wait_sec=get_config_float(
                                plugin.plugin_config,
                                "PROCESS_KILL_WAIT_SEC",
                                default=10.0,
                                minimum=0.0,
                            )
                            or 10.0,
                            use_process_group=not is_windows(),
                        )
                    )
                    if not terminated:
                        raise NativeProbeTerminationError(
                            "The backend runtime check could not be stopped. Restart SoAI before retrying."
                        )
            stdout = await run_joined_thread_call(
                _read_capture,
                captures[0],
                task_name="native-probe.read-stdout",
                retain_resources_until_complete=True,
            )
            stderr = await run_joined_thread_call(
                _read_capture,
                captures[1],
                task_name="native-probe.read-stderr",
                retain_resources_until_complete=True,
            )
            result = NativeRuntimeProbeResult(
                stdout,
                stderr or (f"Timeout after {allowance.seconds:g}s" if timed_out else ""),
                session.process.returncode,
                True,
                timed_out,
                time.monotonic() - started,
                allowance,
            )
        return result
    finally:
        await run_joined_thread_call(
            _close_captures,
            captures,
            task_name="native-probe.close-captures",
            retain_resources_until_complete=True,
        )
