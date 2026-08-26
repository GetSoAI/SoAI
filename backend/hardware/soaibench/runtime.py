"""SoAI - SoAIBench service runtime helpers [backend/hardware/soaibench/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_limits import (
    SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS,
    SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS,
)
from core.types.json import JSONValue
from core.validation.numbers import coerce_float_from_json
from hardware.soaibench.types import SoAIBenchBenchmarkMode, SoAIBenchProfile

__all__ = (
    "CERTIFIED_DEFAULT_TEMPERATURE_LIMIT_CELSIUS",
    "CERTIFIED_MEASURED_PASSES",
    "CERTIFIED_SCORE_VARIANCE_LIMIT_PERCENT",
    "CERTIFIED_WARMUP_PASSES",
    "OWNER_TYPE",
    "parse_benchmark_mode",
    "parse_profile",
    "parse_temperature_limit_celsius",
    "task_id_for_run",
)

OWNER_TYPE = "hardware_soaibench"
CERTIFIED_DEFAULT_TEMPERATURE_LIMIT_CELSIUS = 100.0
CERTIFIED_MEASURED_PASSES = 5
CERTIFIED_SCORE_VARIANCE_LIMIT_PERCENT = 10.0
CERTIFIED_WARMUP_PASSES = 1


def parse_profile(profile: str) -> SoAIBenchProfile:
    try:
        return SoAIBenchProfile(str(profile).strip())
    except ValueError as exception:
        raise ValidationError("profile must be standard or stress.") from exception


def parse_benchmark_mode(mode: str | None) -> SoAIBenchBenchmarkMode:
    value = "quick" if mode is None else str(mode).strip() or "quick"
    try:
        return SoAIBenchBenchmarkMode(value)
    except ValueError as exception:
        raise ValidationError("benchmark_mode must be quick or certified.") from exception


def parse_temperature_limit_celsius(value: JSONValue | None) -> float | None:
    if value is None:
        return None
    parsed = coerce_float_from_json(
        value,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )
    if parsed is None:
        raise ValidationError("temperature_limit_celsius must be a finite number.")
    if (
        parsed < SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS
        or parsed > SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS
    ):
        raise ValidationError(
            f"temperature_limit_celsius must be between {SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS} and {SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS}.",
        )
    return parsed


def task_id_for_run(run_id: str) -> str:
    return f"hardware-soaibench-{run_id}"
