"""SoAI - Metrics worker payload parsing [backend/metrics/manager/worker_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from metrics.manager.types import MetricsWorkerPayload

if TYPE_CHECKING:
    from metrics.manager.types import MetricsWorkerArg, MetricsWorkerOptionValue

__all__ = (
    "coerce_metric_keys",
    "extract_options",
    "get_float_arg",
    "get_numeric_option",
    "get_str_arg",
    "get_strict_int_arg",
    "get_unique_item_option",
)


def _payload_args(payload: MetricsWorkerPayload) -> Sequence[MetricsWorkerArg]:
    raw_args = payload.get("args", ())
    if not isinstance(raw_args, Sequence) or isinstance(raw_args, str | bytes | bytearray):
        return ()
    return raw_args


def coerce_metric_keys(payload: MetricsWorkerPayload) -> tuple[str, ...]:
    return tuple(
        arg.strip() for arg in _payload_args(payload) if isinstance(arg, str) and arg.strip()
    )


def extract_options(payload: MetricsWorkerPayload) -> Mapping[str, MetricsWorkerOptionValue]:
    raw_options = payload.get("options", {})
    if not isinstance(raw_options, Mapping):
        return {}
    filtered: dict[str, MetricsWorkerOptionValue] = {}
    for key, value in raw_options.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            filtered[key] = value
    return filtered


def get_str_arg(payload: MetricsWorkerPayload, index: int) -> str | None:
    if index < 0:
        return None
    args = _payload_args(payload)
    if index >= len(args):
        return None
    value = args[index]
    return value if isinstance(value, str) else None


def get_strict_int_arg(payload: MetricsWorkerPayload, index: int) -> int | None:
    if index < 0:
        return None
    args = _payload_args(payload)
    if index >= len(args):
        return None
    value = args[index]
    return int(value) if is_strict_int(value) else None


def get_float_arg(payload: MetricsWorkerPayload, index: int) -> float | None:
    if index < 0:
        return None
    args = _payload_args(payload)
    if index >= len(args):
        return None
    value = args[index]
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    return numeric_value if math.isfinite(numeric_value) else None


def get_numeric_option(
    payload: MetricsWorkerPayload,
    key: str,
    default: float,
) -> int | float:
    value = extract_options(payload).get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return default
    return value


def get_unique_item_option(payload: MetricsWorkerPayload, key: str) -> str | None:
    value = extract_options(payload).get(key)
    if isinstance(value, str):
        return value or None
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else None
    return None
