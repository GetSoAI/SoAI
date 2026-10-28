"""SoAI - Observed GPU physical identity readers [backend/core/hardware/gpu_physical_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_identity_normalization import (
    normalize_observed_full_pci_bdf,
    observed_pci_bdf_components,
    observed_pci_bdf_conflicts,
)
from core.hardware.gpu_physical_identity import GPUPhysicalIdentity
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "gpu_pci_observation_fields",
    "gpu_uuid_observation_fields",
    "read_gpu_pci_observations",
    "read_gpu_physical_identity",
    "read_gpu_platform_observations",
    "read_gpu_uuid_observations",
    "read_gpu_vendor",
)


def read_gpu_physical_identity(entry: JSONDict) -> GPUPhysicalIdentity | None:
    read_gpu_vendor(entry)
    read_gpu_platform_observations(entry)
    uuid_values = read_gpu_uuid_observations(entry)
    pci_values = [
        text for text in read_gpu_pci_observations(entry) if normalize_observed_full_pci_bdf(text)
    ]
    native_path = entry.get("native_device_path")
    if native_path is not None and not isinstance(native_path, str):
        raise ValidationError("GPU actual native device path must be text.")
    pnp_instance = entry.get("windows_pnp_instance_id")
    if pnp_instance is not None and not isinstance(pnp_instance, str):
        raise ValidationError("GPU actual Windows PNP instance must be text.")
    if not uuid_values and not pci_values and native_path is None and pnp_instance is None:
        return None
    return GPUPhysicalIdentity(
        uuid=uuid_values[0] if uuid_values else None,
        pci_bdf_full=pci_values[0] if pci_values else None,
        native_device_path=native_path,
        windows_pnp_instance_id=pnp_instance,
    )


def read_gpu_platform_observations(entry: JSONDict) -> tuple[str | None, tuple[str, ...]]:
    driver = entry.get("platform_driver")
    if driver is not None and (
        not isinstance(driver, str) or not driver or driver != driver.strip()
    ):
        raise ValidationError("GPU actual platform driver observation is invalid.")
    compatible = entry.get("platform_compatible", [])
    if not isinstance(compatible, list) or any(
        not isinstance(value, str) or not value or value != value.strip() for value in compatible
    ):
        raise ValidationError("GPU actual platform compatible observations are invalid.")
    return driver, tuple(value for value in compatible if isinstance(value, str))


def read_gpu_uuid_observations(entry: JSONDict) -> list[str]:
    observations: list[str] = []
    for field in gpu_uuid_observation_fields(entry):
        value = entry.get(field)
        if field == "gpu_uuid_observations":
            if not isinstance(value, list):
                raise ValidationError("GPU UUID observations must be a list.")
            values = value
        else:
            if value is None:
                continue
            values = [value]
        for observation in values:
            if not isinstance(observation, str):
                raise ValidationError("GPU UUID observation must be text.")
            if field == "gpu_uuid_observations" and (
                not observation or observation != observation.strip()
            ):
                raise ValidationError("GPU UUID list observation must be canonical nonempty text.")
            text = coerce_optional_trimmed_str(observation)
            if text is not None and text not in observations:
                observations.append(text)
    if len({value.casefold() for value in observations}) > 1:
        raise ValidationError("GPU UUID observations conflict.")
    return observations


def gpu_uuid_observation_fields(entry: JSONDict) -> tuple[str, ...]:
    return ("uuid",) + (
        ("gpu_uuid_observations",) if "gpu_uuid_observations" in entry else ("gpu_uuid",)
    )


def read_gpu_pci_observations(entry: JSONDict) -> list[str]:
    observations: list[str] = []
    for field in gpu_pci_observation_fields(entry):
        value = entry.get(field)
        if field == "pci_bdf_observations":
            if not isinstance(value, list):
                raise ValidationError("GPU PCI observations must be a list.")
            values = value
        else:
            if value is None or value == "":
                continue
            values = [value]
        for observation in values:
            if not isinstance(observation, str) or observed_pci_bdf_components(observation) is None:
                raise ValidationError("GPU PCI observation is invalid.")
            if field == "pci_bdf_full" and not normalize_observed_full_pci_bdf(observation):
                raise ValidationError("GPU full PCI observation is incomplete.")
            if any(observed_pci_bdf_conflicts(observation, previous) for previous in observations):
                raise ValidationError("GPU PCI observations conflict.")
            if observation not in observations:
                observations.append(observation)
    return observations


def gpu_pci_observation_fields(entry: JSONDict) -> tuple[str, ...]:
    independent_fields = ("pci_bdf_full", "pci_bus_id", "bus_id")
    return independent_fields + (
        ("pci_bdf_observations",) if "pci_bdf_observations" in entry else ("pci_bdf",)
    )


def read_gpu_vendor(entry: JSONDict) -> str | None:
    observations: list[str] = []
    for field in ("type", "vendor"):
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            raise ValidationError("GPU vendor observation must be text.")
        text = coerce_optional_trimmed_str(value)
        if text is not None:
            observations.append(text)
    if len({value.casefold() for value in observations}) > 1:
        raise ValidationError("GPU vendor observations conflict.")
    return observations[0] if observations else None
