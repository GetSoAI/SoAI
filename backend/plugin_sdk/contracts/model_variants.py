"""SoAI - Plugin SDK model variant helpers [backend/plugin_sdk/contracts/model_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from core.config.byte_sizes import GIB_BYTES
from core.errors.exceptions import ValidationError
from core.plugins.model_variants import normalize_variant_name
from plugin_sdk.contracts.errors import PluginConfigurationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_model_variant",
    "normalize_variant_name",
    "resolve_model_download_required_bytes",
)


def _normalize_positive_int(value: JSONValue) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError("Boolean size values are not permitted.")
    if isinstance(value, int):
        candidate = int(value)
    elif isinstance(value, float):
        candidate = _decimal_to_int(Decimal(str(value)))
    else:
        normalized_value = str(value).strip()
        if normalized_value.isdecimal():
            candidate = int(normalized_value)
        else:
            try:
                candidate = _decimal_to_int(Decimal(normalized_value))
            except InvalidOperation as exception:
                raise ValidationError("Size values must be numeric.") from exception
    if candidate <= 0:
        return None
    return candidate


def _decimal_to_int(value: Decimal) -> int:
    if not value.is_finite():
        raise ValidationError("Size values must be finite.")
    return int(value)


def build_model_variant(
    *,
    model_id: str,
    ref: str | None,
    name: str,
    quantization: str | None = None,
    size_bytes: JSONValue = None,
    description: str | None = None,
    checksum: str | None = None,
    family: str | None = None,
    metadata: JSONDict | None = None,
) -> JSONDict:
    if not model_id:
        raise PluginConfigurationError("model_id is required to build a variant description.")
    if not name:
        raise PluginConfigurationError("Variant name is required.")
    size_int = _normalize_positive_int(size_bytes)
    size_gb = round(size_int / GIB_BYTES, 2) if size_int else None
    ram_required = round(size_gb * 1.3, 2) if size_gb else None
    vram_required = round(size_gb, 2) if size_gb else None
    payload: JSONDict = {
        "id": f"{model_id}@{ref}" if ref else model_id,
        "name": name,
        "normalized_name": normalize_variant_name(name),
        "quantization": quantization,
        "size_bytes": size_int,
        "size_gb": size_gb,
        "ram_required_gb": ram_required,
        "vram_required_gb": vram_required,
        "description": description,
        "checksum": checksum,
    }
    if family:
        payload["family"] = family
    if metadata:
        payload.update(metadata)
    return payload


def resolve_model_download_required_bytes(
    variants: Sequence[JSONDict],
    quantization: str | None,
) -> int:
    normalized_quantization = (quantization or "").strip().lower()
    if not variants:
        return 0
    if not normalized_quantization:
        return _single_variant_size_bytes(variants)
    for variant in variants:
        if not _variant_matches_quantization(
            variant,
            normalized_quantization,
        ):
            continue
        size_int = _normalize_positive_int_safely(variant.get("size_bytes"))
        if size_int is not None:
            return size_int
    return 0


def _single_variant_size_bytes(variants: Sequence[JSONDict]) -> int:
    if len(variants) != 1:
        return 0
    size_int = _normalize_positive_int_safely(variants[0].get("size_bytes"))
    return size_int if size_int is not None else 0


def _variant_matches_quantization(
    variant: JSONDict,
    normalized_quantization: str,
) -> bool:
    for key in ("id", "name", "quantization", "normalized_name"):
        value = variant.get(key)
        if isinstance(value, str):
            candidate = value.strip().lower()
            if candidate == normalized_quantization or normalized_quantization in candidate:
                return True
    return False


def _normalize_positive_int_safely(value: JSONValue) -> int | None:
    try:
        return _normalize_positive_int(value)
    except (InvalidOperation, TypeError, ValueError, ValidationError):
        return None
