"""SoAI - CPU instruction feature detection [backend/hardware/manager/cpu_feature_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict
from hardware.cpu_inventory.linux_topology import read_cpu_mask

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.runtime.platform import RuntimePlatform
    from core.system.protocols import CommandExecutorProtocol

__all__ = (
    "CPU_FEATURE_OBSERVATION_CHANGING",
    "CPU_FEATURE_OBSERVATION_COMPLETE",
    "CPU_FEATURE_OBSERVATION_CONFLICTING",
    "CPU_FEATURE_OBSERVATION_MALFORMED",
    "CPU_FEATURE_OBSERVATION_UNAVAILABLE",
    "CpuInstructionFeatures",
    "detect_cpu_instruction_features",
)

OPERATION_HARDWARE_CPU_FEATURES_READ_PROC_CPUINFO = "hardware.cpu_features.read_proc_cpuinfo"
OPERATION_HARDWARE_CPU_FEATURES_RUN_LSCPU = "hardware.cpu_features.run_lscpu"
OPERATION_HARDWARE_CPU_FEATURES_RUN_SYSCTL = "hardware.cpu_features.run_sysctl"
OPERATION_HARDWARE_CPU_FEATURES_WINDOWS = "hardware.cpu_features.windows"


_WINDOWS_FEATURE_SSE = 6
_WINDOWS_FEATURE_SSE2 = 10
_WINDOWS_FEATURE_AVX = 39
_WINDOWS_FEATURE_AVX2 = 40
_RETAINED_FEATURE_TOKENS = frozenset(("fma", "avx512f", "avx512vl"))
CPU_FEATURE_OBSERVATION_COMPLETE = "complete"
CPU_FEATURE_OBSERVATION_UNAVAILABLE = "unavailable"
CPU_FEATURE_OBSERVATION_MALFORMED = "malformed"
CPU_FEATURE_OBSERVATION_CONFLICTING = "conflicting"
CPU_FEATURE_OBSERVATION_CHANGING = "changing"


@dataclass(frozen=True, slots=True)
class CpuInstructionFeatures:
    features: frozenset[str]
    observation: str


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
    normalized.update(tokens.intersection(_RETAINED_FEATURE_TOKENS))
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


def _read_linux_proc_cpuinfo(*, logger: TraceLogger) -> str | None:
    if not os.path.exists("/proc/cpuinfo"):
        return None
    try:
        with open_text("/proc/cpuinfo", encoding="utf-8") as file_handle:
            return file_handle.read().lower()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read /proc/cpuinfo for CPU feature detection (non-critical).",
            operation=OPERATION_HARDWARE_CPU_FEATURES_READ_PROC_CPUINFO,
            level="trace",
        )
        return None


def _parse_linux_proc_cpuinfo(*, logger: TraceLogger) -> set[str]:
    cpuinfo = _read_linux_proc_cpuinfo(logger=logger)
    if cpuinfo is None:
        return set()
    for prefix in ("flags", "features"):
        for line in cpuinfo.splitlines():
            if not line.startswith(prefix):
                continue
            _, _, values = line.partition(":")
            return {token for token in values.strip().split() if token}
    return set()


def _parse_linux_processor_flags(cpuinfo: str) -> dict[int, frozenset[str]] | None:
    records: dict[int, frozenset[str]] = {}
    for block in re.split(r"\n[ \t]*\n", cpuinfo.strip()):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            name, separator, value = line.partition(":")
            if not separator or name.strip() in fields:
                return None
            fields[name.strip()] = value.strip()
        processor = fields.get("processor", "")
        flags = fields.get("flags")
        if not processor.isdecimal() or flags is None or int(processor) in records:
            return None
        records[int(processor)] = frozenset(flags.split())
    return records or None


def _observe_linux_processor_features(*, logger: TraceLogger) -> CpuInstructionFeatures:
    online_before = read_cpu_mask("online")
    cpuinfo = _read_linux_proc_cpuinfo(logger=logger)
    online_after = read_cpu_mask("online")
    if online_before.status == "unavailable" or cpuinfo is None:
        return CpuInstructionFeatures(frozenset(), CPU_FEATURE_OBSERVATION_UNAVAILABLE)
    records = _parse_linux_processor_flags(cpuinfo)
    if online_before.identities is None or records is None:
        return CpuInstructionFeatures(frozenset(), CPU_FEATURE_OBSERVATION_MALFORMED)
    if online_after != online_before:
        return CpuInstructionFeatures(frozenset(), CPU_FEATURE_OBSERVATION_CHANGING)
    if sorted(records) != online_before.identities:
        return CpuInstructionFeatures(frozenset(), CPU_FEATURE_OBSERVATION_CONFLICTING)
    shared_flags = frozenset[str].intersection(*records.values())
    return CpuInstructionFeatures(
        frozenset(_normalize_feature_tokens(set(shared_flags))),
        CPU_FEATURE_OBSERVATION_COMPLETE,
    )


def _detect_linux_features(
    executor: CommandExecutorProtocol,
    *,
    logger: TraceLogger,
) -> CpuInstructionFeatures:
    per_processor = _observe_linux_processor_features(logger=logger)
    if per_processor.observation == CPU_FEATURE_OBSERVATION_COMPLETE:
        return per_processor
    return CpuInstructionFeatures(
        frozenset(_detect_linux_representative_features(executor, logger=logger)),
        per_processor.observation,
    )


def _detect_linux_representative_features(
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
) -> CpuInstructionFeatures:
    if not _is_x86_architecture():
        return CpuInstructionFeatures(frozenset(), CPU_FEATURE_OBSERVATION_UNAVAILABLE)
    if runtime_platform.is_linux:
        return _detect_linux_features(executor, logger=logger)
    features: set[str]
    if runtime_platform.is_windows:
        features = _detect_windows_features(logger)
    elif runtime_platform.is_macos:
        features = _detect_macos_features(executor, logger=logger)
    else:
        features = set()
    return CpuInstructionFeatures(frozenset(features), CPU_FEATURE_OBSERVATION_UNAVAILABLE)
