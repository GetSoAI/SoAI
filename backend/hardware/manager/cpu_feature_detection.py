"""SoAI - CPU instruction feature detection [backend/hardware/manager/cpu_feature_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.runtime.platform import RuntimePlatform
    from core.system.protocols import CommandExecutorProtocol

__all__ = ("detect_cpu_instruction_features",)

OPERATION_HARDWARE_CPU_FEATURES_READ_PROC_CPUINFO = "hardware.cpu_features.read_proc_cpuinfo"
OPERATION_HARDWARE_CPU_FEATURES_RUN_LSCPU = "hardware.cpu_features.run_lscpu"
OPERATION_HARDWARE_CPU_FEATURES_RUN_SYSCTL = "hardware.cpu_features.run_sysctl"
OPERATION_HARDWARE_CPU_FEATURES_WINDOWS = "hardware.cpu_features.windows"


_WINDOWS_FEATURE_SSE = 6
_WINDOWS_FEATURE_SSE2 = 10
_WINDOWS_FEATURE_AVX = 39
_WINDOWS_FEATURE_AVX2 = 40


def _is_x86_architecture() -> bool:
    return platform.machine().lower() in {"x86_64", "amd64", "i386", "i686"}


def _normalize_feature_tokens(tokens: set[str]) -> set[str]:
    normalized: set[str] = set()
    if any(token.startswith("sse") or token == "ssse3" for token in tokens):
        normalized.add("sse")
    if any(token.startswith("sse2") for token in tokens):
        normalized.update({"sse", "sse2"})
    if "avx" in tokens or "avx1.0" in tokens:
        normalized.add("avx")
    if "avx2" in tokens or "avx2.0" in tokens:
        normalized.update({"avx", "avx2"})
    return normalized


def _parse_linux_lscpu_flags(stdout: str) -> set[str]:
    try:
        payload = parse_json_dict(stdout, field="lscpu --json")
    except ValidationError:
        return set()
    entries = payload.get("lscpu")
    if not isinstance(entries, list):
        return set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        field = str(entry.get("field", "")).strip(":").lower()
        if field != "flags":
            continue
        data = str(entry.get("data", "")).strip().lower()
        if not data:
            return set()
        return {token for token in data.split() if token}
    return set()


def _parse_linux_proc_cpuinfo(*, logger: TraceLogger) -> set[str]:
    if not os.path.exists("/proc/cpuinfo"):
        return set()
    try:
        with open_text("/proc/cpuinfo", encoding="utf-8") as file_handle:
            cpuinfo = file_handle.read().lower()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read /proc/cpuinfo for CPU feature detection (non-critical).",
            operation=OPERATION_HARDWARE_CPU_FEATURES_READ_PROC_CPUINFO,
            level="trace",
        )
        return set()
    for prefix in ("flags", "features"):
        for line in cpuinfo.splitlines():
            if not line.startswith(prefix):
                continue
            _, _, values = line.partition(":")
            return {token for token in values.strip().split() if token}
    return set()


def _detect_linux_features(
    executor: CommandExecutorProtocol,
    *,
    logger: TraceLogger,
) -> set[str]:
    lscpu_path = shutil.which("lscpu")
    if lscpu_path:
        try:
            result = executor.execute(
                [lscpu_path, "--json"],
                timeout=10,
                shell=False,
                use_sudo=False,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to execute lscpu for CPU feature detection (non-critical).",
                operation=OPERATION_HARDWARE_CPU_FEATURES_RUN_LSCPU,
                level="trace",
            )
        else:
            if result.return_code == 0 and result.stdout:
                return _normalize_feature_tokens(_parse_linux_lscpu_flags(result.stdout))
    return _normalize_feature_tokens(_parse_linux_proc_cpuinfo(logger=logger))


def _detect_windows_features(logger: TraceLogger) -> set[str]:
    if sys.platform != "win32":
        return set()
    try:
        kernel32 = ctypes.windll.kernel32
        feature_function = kernel32.IsProcessorFeaturePresent
    except (AttributeError, OSError, ValueError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query Windows processor features.",
            operation=OPERATION_HARDWARE_CPU_FEATURES_WINDOWS,
            level="trace",
        )
        return set()
    tokens: set[str] = set()
    if feature_function(_WINDOWS_FEATURE_SSE):
        tokens.add("sse")
    if feature_function(_WINDOWS_FEATURE_SSE2):
        tokens.update({"sse", "sse2"})
    if feature_function(_WINDOWS_FEATURE_AVX):
        tokens.add("avx")
    if feature_function(_WINDOWS_FEATURE_AVX2):
        tokens.update({"avx", "avx2"})
    return tokens


def _detect_macos_features(
    executor: CommandExecutorProtocol,
    *,
    logger: TraceLogger,
) -> set[str]:
    try:
        result = executor.execute(
            ["sysctl", "machdep.cpu.features", "machdep.cpu.leaf7_features"],
            timeout=3,
            shell=False,
            use_sudo=False,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to execute sysctl for CPU feature detection (non-critical).",
            operation=OPERATION_HARDWARE_CPU_FEATURES_RUN_SYSCTL,
            level="trace",
        )
        return set()
    if result.return_code != 0:
        logger.trace("Failed to read CPU features on macOS: %s", result.stderr.strip())
        return set()
    tokens: set[str] = set()
    for line in result.stdout.splitlines():
        _, _, values = line.partition(":")
        for token in values.strip().lower().split():
            if token:
                tokens.add(token)
    return _normalize_feature_tokens(tokens)


def detect_cpu_instruction_features(
    executor: CommandExecutorProtocol,
    *,
    runtime_platform: RuntimePlatform,
    logger: TraceLogger,
) -> set[str]:
    if not _is_x86_architecture():
        return set()
    if runtime_platform.is_linux:
        return _detect_linux_features(executor, logger=logger)
    if runtime_platform.is_windows:
        return _detect_windows_features(logger)
    if runtime_platform.is_macos:
        return _detect_macos_features(executor, logger=logger)
    return set()
