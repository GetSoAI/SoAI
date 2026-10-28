"""SoAI - Validated ADL native adapter inventory [backend/hardware/vendors/amd/adl_adapter_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

from core.errors.exceptions import ValidationError
from hardware.vendors.amd.adl_abi import (
    AdlAdapterInfo,
    AdlAdapterObservation,
    validate_adl_layouts,
)

__all__ = ("decode_adl_adapters",)


def decode_adl_adapters(
    adapters: ctypes.Array[AdlAdapterInfo],
) -> tuple[AdlAdapterObservation, ...]:
    validate_adl_layouts()
    declared_size = ctypes.sizeof(AdlAdapterInfo)
    observations: list[AdlAdapterObservation] = []
    identifiers: set[int] = set()
    for adapter in adapters:
        locator_valid = (
            adapter.adapter_index >= 0
            and adapter.adapter_index not in identifiers
            and 0 <= adapter.bus <= 255
            and 0 <= adapter.device <= 31
            and 0 <= adapter.function <= 7
        )
        record_valid = (
            adapter.size in (0, declared_size)
            and adapter.vendor >= 0
            and adapter.present in (0, 1)
            and adapter.exists in (0, 1)
        )
        if not locator_valid or not record_valid:
            raise ValidationError("ADL native adapter record is malformed.")
        udid = _native_text(adapter.udid)
        pnp_instance = _native_text(adapter.pnp_string)
        if (adapter.present or adapter.exists) and not (udid or pnp_instance):
            raise ValidationError("ADL active adapter identity is unavailable.")
        identifiers.add(adapter.adapter_index)
        observations.append(
            AdlAdapterObservation(
                adapter.adapter_index,
                adapter.bus,
                adapter.device,
                adapter.function,
                adapter.vendor,
                bool(adapter.present),
                bool(adapter.exists),
                udid,
                pnp_instance,
            )
        )
    if not any(adapter.udid or adapter.pnp_instance for adapter in observations):
        raise ValidationError("ADL adapter inventory has no usable identity.")
    return tuple(observations)


def _native_text(value: bytes) -> str:
    if len(value) >= 256:
        raise ValidationError("ADL native identity string is unterminated.")
    try:
        text = value.decode("ascii")
    except UnicodeDecodeError as exception:
        raise ValidationError(
            "ADL native identity string is malformed.", cause=exception
        ) from exception
    if text != text.strip() or any(
        ord(character) < 32 or ord(character) == 127 for character in text
    ):
        raise ValidationError("ADL native identity string is not canonical.")
    return text
