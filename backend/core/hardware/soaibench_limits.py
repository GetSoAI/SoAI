"""SoAI - SoAIBench shared limit constants [backend/core/hardware/soaibench_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Final

__all__ = (
    "SOAIBENCH_HISTORY_DEFAULT_LIMIT",
    "SOAIBENCH_LIST_MAX_LIMIT",
    "SOAIBENCH_LIST_MIN_LIMIT",
    "SOAIBENCH_RUNS_DEFAULT_LIMIT",
    "SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS",
    "SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS",
)

SOAIBENCH_HISTORY_DEFAULT_LIMIT: Final[int] = 25
SOAIBENCH_RUNS_DEFAULT_LIMIT: Final[int] = 50
SOAIBENCH_LIST_MIN_LIMIT: Final[int] = 1
SOAIBENCH_LIST_MAX_LIMIT: Final[int] = 100
SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS: Final[float] = 1000.0
SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS: Final[float] = -273.15
