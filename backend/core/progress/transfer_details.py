"""SoAI - Transfer metric details normalization [backend/core/progress/transfer_details.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.progress.formatting import calculate_eta, format_transfer_details
from core.types.json import JSONValue, is_json_dict
from core.validation.coercion import coerce_non_negative_int_from_numberish
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "resolve_transfer_details_payload",
    "resolve_transfer_progress_details",
)

_DOWNLOADED_KEYS: tuple[str, ...] = (
    "downloaded_size",
    "downloaded_bytes",
    "bytes_downloaded",
    "bytes_done",
    "transferred_bytes",
)
_TOTAL_KEYS: tuple[str, ...] = (
    "total_size",
    "total_bytes",
    "total_size_bytes",
    "bytes_total",
)
_SPEED_KEYS: tuple[str, ...] = ("bytes_per_second", "speed", "download_speed")
_ETA_KEYS: tuple[str, ...] = ("eta_seconds", "eta")


def resolve_transfer_progress_details(
    progress_payload: Mapping[str, JSONValue],
    details: JSONValue | None,
) -> JSONValue | None:
    if isinstance(details, str) and details.strip():
        return details
    if is_json_dict(details):
        detail_text = _format_transfer_details(details)
        if detail_text:
            return detail_text
    detail_text = _format_transfer_details(progress_payload)
    if detail_text:
        return detail_text
    return details


def resolve_transfer_details_payload(details: JSONValue | None) -> JSONValue | None:
    if isinstance(details, str):
        return details
    if not is_json_dict(details):
        return details
    detail_text = _format_transfer_details(details)
    if detail_text:
        return detail_text
    return details


def _format_transfer_details(source: Mapping[str, JSONValue]) -> str:
    downloaded_size = _read_non_negative_int(source, _DOWNLOADED_KEYS)
    total_size = _read_non_negative_int(source, _TOTAL_KEYS)
    speed = _read_non_negative_float(source, _SPEED_KEYS)
    eta_seconds = _read_non_negative_float(source, _ETA_KEYS)
    if eta_seconds <= 0.0 < speed and downloaded_size is not None and total_size:
        eta_seconds = calculate_eta(speed, downloaded_size, total_size)
    if downloaded_size is None and total_size is None and speed <= 0.0 and eta_seconds <= 0.0:
        return ""
    return format_transfer_details(
        downloaded_size or 0,
        total_size,
        speed=speed,
        eta_seconds=eta_seconds,
    )


def _read_non_negative_int(source: Mapping[str, JSONValue], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        return coerce_non_negative_int_from_numberish(value)
    return None


def _read_non_negative_float(source: Mapping[str, JSONValue], keys: tuple[str, ...]) -> float:
    for key in keys:
        value = source.get(key)
        parsed = coerce_float_from_json(value, default=None)
        if parsed is None:
            continue
        return max(0.0, parsed)
    return 0.0
