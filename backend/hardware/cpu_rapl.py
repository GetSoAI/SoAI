"""SoAI - Intel RAPL CPU energy and power sampling [backend/hardware/cpu_rapl.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = (
    "RaplEnergyCache",
    "RaplPackageReading",
    "RaplPowerSample",
    "sample_rapl_cpu_power",
)

LOGGER_NAME = "SoAI.hardware.cpu_rapl"
OPERATION_RAPL_ENERGY = "hardware_info.cpu.rapl_energy"
OPERATION_RAPL_POWER_LIMIT = "hardware_info.cpu.rapl_power_limit"
OPERATION_RAPL_TEXT = "hardware_info.cpu.rapl_text"
MICRO_UNITS_PER_UNIT = 1_000_000
RAPL_BASE = "/sys/class/powercap"
PACKAGE_DOMAIN_PREFIX = "package"
RAPL_DOMAIN_PREFIX = "intel-rapl:"


class RaplEnergyCache:
    __slots__ = ("entries", "lock")

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.entries: dict[str, tuple[int, float]] = {}


@dataclass(frozen=True, slots=True)
class RaplPackageReading:
    socket_index: int
    power_draw_watts: float | None
    power_limit_watts: float | None


@dataclass(frozen=True, slots=True)
class RaplPowerSample:
    packages: tuple[RaplPackageReading, ...]
    total_power_watts: float | None
    total_power_limit_watts: float | None


def sample_rapl_cpu_power(rapl_energy_cache: RaplEnergyCache) -> RaplPowerSample:
    logger = get_logger(LOGGER_NAME)
    domains = _discover_package_domains()
    if not domains:
        return RaplPowerSample(packages=(), total_power_watts=None, total_power_limit_watts=None)
    observed_at = epoch_seconds_float()
    readings: list[RaplPackageReading] = []
    total_power: float | None = None
    total_limit: float | None = None
    for socket_index, domain_path in domains:
        power_watts = _sample_domain_watts(domain_path, rapl_energy_cache, observed_at, logger)
        limit_watts = _read_package_power_limit(domain_path, logger)
        readings.append(
            RaplPackageReading(
                socket_index=socket_index,
                power_draw_watts=power_watts,
                power_limit_watts=limit_watts,
            ),
        )
        if power_watts is not None:
            total_power = power_watts if total_power is None else total_power + power_watts
        if limit_watts is not None:
            total_limit = limit_watts if total_limit is None else total_limit + limit_watts
    return RaplPowerSample(
        packages=tuple(readings),
        total_power_watts=total_power,
        total_power_limit_watts=total_limit,
    )


def _discover_package_domains() -> list[tuple[int, str]]:
    logger = get_logger(LOGGER_NAME)
    if not os.path.isdir(RAPL_BASE):
        return []
    try:
        entries = os.listdir(RAPL_BASE)
    except OSError:
        return []
    domains: list[tuple[int, str]] = []
    for entry in entries:
        if not entry.startswith(RAPL_DOMAIN_PREFIX):
            continue
        suffix = entry[len(RAPL_DOMAIN_PREFIX) :]
        if ":" in suffix:
            continue
        try:
            socket_index = int(suffix)
        except ValueError:
            continue
        domain_path = os.path.join(RAPL_BASE, entry)
        if not os.path.isdir(domain_path):
            continue
        domain_name = _read_text(os.path.join(domain_path, "name"), logger)
        if domain_name is not None and domain_name.startswith(PACKAGE_DOMAIN_PREFIX):
            domains.append((socket_index, domain_path))
    domains.sort(key=lambda item: item[0])
    return domains


def _sample_domain_watts(
    domain_path: str,
    rapl_energy_cache: RaplEnergyCache,
    observed_at: float,
    logger: TraceLogger,
) -> float | None:
    energy_path = os.path.join(domain_path, "energy_uj")
    energy_uj = _read_energy(energy_path, logger)
    if energy_uj is None:
        return None
    with rapl_energy_cache.lock:
        previous = rapl_energy_cache.entries.get(energy_path)
        rapl_energy_cache.entries[energy_path] = (energy_uj, observed_at)
    if previous is None:
        return None
    prev_energy, prev_time = previous
    delta_seconds = observed_at - prev_time
    if delta_seconds <= 0:
        return None
    delta_energy = energy_uj - prev_energy
    if delta_energy < 0:
        max_range = _read_int(os.path.join(domain_path, "max_energy_range_uj"), logger)
        if max_range is None or max_range <= 0:
            return None
        delta_energy += max_range
        if delta_energy < 0:
            return None
    return delta_energy / MICRO_UNITS_PER_UNIT / delta_seconds


def _read_package_power_limit(domain_path: str, logger: TraceLogger) -> float | None:
    limit_path = os.path.join(domain_path, "constraint_0_power_limit_uw")
    try:
        with open_text(limit_path, encoding="utf-8") as file_handle:
            power_limit_uw = int(file_handle.read().strip())
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read RAPL power limit (non-critical).",
            operation=OPERATION_RAPL_POWER_LIMIT,
            details={"power_limit_file": limit_path},
            level="trace",
        )
        return None
    if power_limit_uw <= 0:
        return None
    return power_limit_uw / MICRO_UNITS_PER_UNIT


def _read_energy(energy_path: str, logger: TraceLogger) -> int | None:
    try:
        with open_text(energy_path, encoding="utf-8") as file_handle:
            return int(file_handle.read().strip())
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read RAPL energy file (non-critical).",
            operation=OPERATION_RAPL_ENERGY,
            details={"power_file": energy_path},
            level="trace",
        )
        return None


def _read_text(path: str, logger: TraceLogger) -> str | None:
    try:
        with open_text(path, encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read RAPL text file (non-critical).",
            operation=OPERATION_RAPL_TEXT,
            details={"path": path},
            level="trace",
        )
        return None


def _read_int(path: str, logger: TraceLogger) -> int | None:
    text = _read_text(path, logger)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None
