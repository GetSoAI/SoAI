"""SoAI - Trusted GPU executable locations [backend/hardware/gpu_inventory/executable_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ntpath
import os
import posixpath
import stat
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.runtime.platform import get_runtime_platform

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.runtime.protocols import RuntimePlatformViewProtocol


__all__ = (
    "GpuExecutableState",
    "GpuExecutableProbeResult",
    "GpuExecutableAttempt",
    "GpuExecutableResolution",
    "require_gpu_executable_selector",
    "acquire_gpu_executable",
    "resolve_gpu_executable",
    "probe_gpu_executable",
)


class GpuExecutableState(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    PERMISSION_DENIED = "permission_denied"
    QUERY_FAILED = "query_failed"
    UNTRUSTED_PATH = "untrusted_path"


@dataclass(frozen=True, slots=True)
class GpuExecutableProbeResult:
    state: GpuExecutableState
    path: str | None
    diagnostic: str | None


@dataclass(frozen=True, slots=True)
class GpuExecutableAttempt:
    path: str
    state: GpuExecutableState
    diagnostic: str | None


@dataclass(frozen=True, slots=True)
class GpuExecutableResolution:
    executable: Literal["nvidia-smi", "nvidia-settings", "xpu-smi"]
    state: GpuExecutableState
    path: str | None
    attempts: tuple[GpuExecutableAttempt, ...]

    def __post_init__(self) -> None:
        if self.executable not in ("nvidia-smi", "nvidia-settings", "xpu-smi"):
            raise ValidationError("NVIDIA executable tool selector is invalid.")
        if not isinstance(self.state, GpuExecutableState):
            raise ValidationError("NVIDIA executable resolution state is invalid.")
        if self.state != GpuExecutableState.FOUND:
            if self.path is not None:
                raise ValidationError("Unavailable NVIDIA executable cannot supply a path.")
            return
        if not isinstance(self.path, str):
            raise ValidationError("Available NVIDIA executable requires its resolved path.")
        windows = bool(ntpath.splitdrive(self.path)[0])
        if _absolute_directory(self.path, windows) is None:
            raise ValidationError("NVIDIA executable requires an explicit absolute path.")


def require_gpu_executable_selector(
    resolution: GpuExecutableResolution,
    *,
    executable: Literal["nvidia-smi", "nvidia-settings", "xpu-smi"],
) -> None:
    if executable not in ("nvidia-smi", "nvidia-settings", "xpu-smi"):
        raise ValidationError("GPU executable dependency tool selector is invalid.")
    if not isinstance(resolution, GpuExecutableResolution) or resolution.executable != executable:
        raise ValidationError(f"GPU executable dependency requires exact {executable} resolution.")


def acquire_gpu_executable(
    executable: Literal["nvidia-smi", "nvidia-settings", "xpu-smi"],
) -> GpuExecutableResolution:
    runtime_platform = get_runtime_platform()
    search_path = os.environ.get("PATH", "")
    program_files = os.getenv("ProgramFiles", None)
    system_root = os.getenv("SystemRoot", None)
    working_directory = os.getcwd()
    return resolve_gpu_executable(
        executable=executable,
        runtime_platform=runtime_platform,
        search_path=search_path,
        program_files=program_files,
        system_root=system_root,
        working_directory=working_directory,
        file_probe=probe_gpu_executable,
    )


def resolve_gpu_executable(
    *,
    executable: Literal["nvidia-smi", "nvidia-settings", "xpu-smi"],
    runtime_platform: RuntimePlatformViewProtocol,
    search_path: str,
    program_files: str | None,
    system_root: str | None,
    working_directory: str,
    file_probe: Callable[[str], GpuExecutableProbeResult],
) -> GpuExecutableResolution:
    if executable not in ("nvidia-smi", "nvidia-settings", "xpu-smi"):
        raise ValidationError("NVIDIA executable tool selector is invalid.")
    windows = runtime_platform.is_windows
    if (
        not isinstance(windows, bool)
        or not isinstance(search_path, str)
        or not callable(file_probe)
    ):
        raise ValidationError("NVIDIA executable resolution inputs are invalid.")
    current_directory = _absolute_directory(working_directory, windows)
    if current_directory is None:
        raise ValidationError(
            "NVIDIA executable resolution requires an absolute current directory."
        )
    if windows and executable == "nvidia-settings":
        return GpuExecutableResolution(executable, GpuExecutableState.MISSING, None, ())
    directories = search_path.split(";" if windows else ":")
    if windows and executable == "nvidia-smi":
        for root, relative in (
            (program_files, ("NVIDIA Corporation", "NVSMI")),
            (system_root, ("System32",)),
        ):
            if root is not None:
                normalized_root = _absolute_directory(root, windows)
                if normalized_root is None:
                    raise ValidationError("NVIDIA installed executable root is invalid.")
                directories.append(ntpath.join(normalized_root, *relative))
    attempts: list[GpuExecutableAttempt] = []
    visited: set[str] = set()
    executable_name = f"{executable}.exe" if windows else executable
    for directory in directories:
        normalized = _absolute_directory(directory, windows)
        if normalized is None or _same_directory(normalized, current_directory, windows):
            if directory:
                attempts.append(
                    GpuExecutableAttempt(directory, GpuExecutableState.UNTRUSTED_PATH, None)
                )
            continue
        candidate = (
            ntpath.join(normalized, executable_name)
            if windows
            else posixpath.join(normalized, executable_name)
        )
        candidate_key = candidate.casefold() if windows else candidate
        if candidate_key in visited:
            continue
        visited.add(candidate_key)
        probe = file_probe(candidate)
        if not isinstance(probe, GpuExecutableProbeResult) or not isinstance(
            probe.state, GpuExecutableState
        ):
            raise ValidationError("NVIDIA executable probe response is invalid.")
        if probe.state == GpuExecutableState.FOUND:
            resolved = probe.path
            if not isinstance(resolved, str):
                raise ValidationError("NVIDIA executable probe omitted its resolved path.")
            resolved_directory = _absolute_directory(
                ntpath.dirname(resolved) if windows else posixpath.dirname(resolved), windows
            )
            if resolved_directory is None or _same_directory(
                resolved_directory, current_directory, windows
            ):
                attempts.append(
                    GpuExecutableAttempt(candidate, GpuExecutableState.UNTRUSTED_PATH, None)
                )
                continue
            attempts.append(GpuExecutableAttempt(candidate, probe.state, probe.diagnostic))
            return GpuExecutableResolution(executable, probe.state, resolved, tuple(attempts))
        if probe.path is not None:
            raise ValidationError("Unavailable NVIDIA executable probe cannot supply a path.")
        attempts.append(GpuExecutableAttempt(candidate, probe.state, probe.diagnostic))
    for failure in (
        GpuExecutableState.QUERY_FAILED,
        GpuExecutableState.PERMISSION_DENIED,
        GpuExecutableState.UNTRUSTED_PATH,
    ):
        if any(attempt.state == failure for attempt in attempts):
            return GpuExecutableResolution(executable, failure, None, tuple(attempts))
    return GpuExecutableResolution(executable, GpuExecutableState.MISSING, None, tuple(attempts))


def probe_gpu_executable(path: str) -> GpuExecutableProbeResult:
    if not isinstance(path, str) or "\0" in path or not os.path.isabs(path):
        raise ValidationError("NVIDIA executable probe requires an explicit absolute path.")
    try:
        resolved = os.path.realpath(path, strict=True)
        metadata = os.stat(resolved)
        if not stat.S_ISREG(metadata.st_mode):
            return GpuExecutableProbeResult(GpuExecutableState.UNTRUSTED_PATH, None, None)
        if not os.access(resolved, os.X_OK):
            return GpuExecutableProbeResult(GpuExecutableState.PERMISSION_DENIED, None, None)
        return GpuExecutableProbeResult(GpuExecutableState.FOUND, resolved, None)
    except FileNotFoundError as exception:
        return GpuExecutableProbeResult(GpuExecutableState.MISSING, None, str(exception))
    except PermissionError as exception:
        return GpuExecutableProbeResult(GpuExecutableState.PERMISSION_DENIED, None, str(exception))
    except OSError as exception:
        return GpuExecutableProbeResult(GpuExecutableState.QUERY_FAILED, None, str(exception))


def _absolute_directory(value: str, windows: bool) -> str | None:
    if not isinstance(value, str) or not value or "\0" in value:
        return None
    if windows:
        drive, _ = ntpath.splitdrive(value)
        if (
            len(drive) != 2
            or not drive[0].isascii()
            or not drive[0].isalpha()
            or drive[1] != ":"
            or not ntpath.isabs(value)
        ):
            return None
        return ntpath.normpath(value)
    return (
        posixpath.normpath(value) if posixpath.isabs(value) and not value.startswith("//") else None
    )


def _same_directory(first: str, second: str, windows: bool) -> bool:
    return first.casefold() == second.casefold() if windows else first == second
