"""SoAI - SoAIBench worker input parsing [backend/hardware/soaibench/worker_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.serialization.json_parsing import parse_optional_json_dict
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numberish import require_int_from_numberish
from core.validation.numbers import coerce_float_from_json
from hardware.soaibench.types import SoAIBenchBenchmarkMode, SoAIBenchProfile

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "base_summary_from_run",
    "temperature_limit_from_summary",
    "parse_worker_run_inputs",
)


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkerRunInputs:
    profile: SoAIBenchProfile
    benchmark_mode: SoAIBenchBenchmarkMode
    started_at_ms: int
    base_summary: JSONDict
    settings_snapshot: JSONDict
    temperature_limit_celsius: float | None


def parse_worker_run_inputs(run: JSONDict) -> SoAIBenchWorkerRunInputs:
    profile = SoAIBenchProfile(str(run["profile"]))
    benchmark_mode = SoAIBenchBenchmarkMode(str(run.get("benchmark_mode") or "quick"))
    started_at_ms = require_int_from_numberish(run["started_at_ms"], field="started_at_ms")
    base_summary = base_summary_from_run(run)
    return SoAIBenchWorkerRunInputs(
        profile=profile,
        benchmark_mode=benchmark_mode,
        started_at_ms=started_at_ms,
        base_summary=base_summary,
        settings_snapshot=coerce_json_dict_or_empty(run.get("settings_snapshot")),
        temperature_limit_celsius=temperature_limit_from_summary(base_summary),
    )


def base_summary_from_run(run: JSONDict) -> JSONDict:
    materialized = run.get("summary")
    if isinstance(materialized, dict):
        return dict(materialized)
    raw = run.get("summary_json")
    if isinstance(raw, str):
        return parse_optional_json_dict(raw, field="summary_json") or {}
    return {}


def temperature_limit_from_summary(summary: JSONDict) -> float | None:
    return coerce_float_from_json(
        summary.get("temperature_limit_celsius"),
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )
