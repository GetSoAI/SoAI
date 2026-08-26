"""SoAI - SoAIBench worker input parsing [backend/hardware/soaibench/worker_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json_parsing import parse_optional_json_dict
from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "base_summary_from_run",
    "temperature_limit_from_summary",
)


def base_summary_from_run(run: JSONDict) -> JSONDict:
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
