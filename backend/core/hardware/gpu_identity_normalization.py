"""SoAI - GPU identity normalization [backend/core/hardware/gpu_identity_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re
import unicodedata

__all__ = (
    "is_specific_gpu_name",
    "normalize_identity_name",
    "normalize_model_key",
    "normalize_observed_full_pci_bdf",
    "normalize_pci_bdf",
    "normalize_physical_pci_bdf",
    "normalize_windows_pnp_instance_id",
    "observed_pci_bdf_components",
    "observed_pci_bdf_conflicts",
    "provisional_gpu_identity_key",
)

_IDENTITY_SEPARATOR_PATTERN_TEXT = r"[^a-z0-9]+"
_GENERIC_GPU_NAMES = frozenset(("", "gpu", "unknown", "unknowngpu"))
_PCI_BDF_PATTERN_TEXT = (
    r"(?:(?P<domain>[0-9a-fA-F]{4}):)?"
    r"(?P<bus>[0-9a-fA-F]{2}):"
    r"(?P<slot>[0-9a-fA-F]{2})"
    r"(?:\.(?P<function>[0-7]))?"
)
_OBSERVED_FULL_PCI_BDF_PATTERN_TEXT = (
    r"(?P<domain>[0-9a-fA-F]{4}|[0-9a-fA-F]{8}):"
    r"(?P<address>[0-9a-fA-F]{2}:[01][0-9a-fA-F]\.[0-7])"
)

_OBSERVED_PCI_BDF_PATTERN_TEXT = (
    r"(?:(?P<domain>[0-9a-fA-F]{4}|[0-9a-fA-F]{8}):)?"
    r"(?P<bus>[0-9a-fA-F]{2}):(?P<device>[01][0-9a-fA-F])"
    r"(?:\.(?P<function>[0-7]))?"
)


def normalize_identity_name(value: str) -> str:
    return re.sub(_IDENTITY_SEPARATOR_PATTERN_TEXT, "", value.lower())


def normalize_model_key(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = re.sub(_IDENTITY_SEPARATOR_PATTERN_TEXT, "-", name.lower()).strip("-")
    return normalized or None


def provisional_gpu_identity_key(vendor: str | None, name: str | None) -> str:
    normalized_name = _normalized_provisional_text(name or "")
    if normalized_name in _GENERIC_GPU_NAMES:
        raise ValueError("A provisional GPU requires a specific name.")
    legacy_name = normalize_identity_name(name or "")
    if legacy_name:
        legacy_vendor = normalize_identity_name(vendor or "") or "unknown"
        identity = f"{legacy_vendor}:{legacy_name}".encode()
    else:
        normalized_vendor = _normalized_provisional_text(vendor or "") or "unknown"
        identity = f"{normalized_vendor}\0{normalized_name}".encode()
    return f"unverified-{hashlib.sha256(identity).hexdigest()[:32]}"


def is_specific_gpu_name(name: str | None) -> bool:
    return _normalized_provisional_text(name or "") not in _GENERIC_GPU_NAMES


def _normalized_provisional_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def normalize_pci_bdf(value: str) -> str:
    match = re.search(_PCI_BDF_PATTERN_TEXT, value)
    if match is None:
        return ""
    function = match.group("function") or "0"
    return f"{match.group('bus').lower()}:{match.group('slot').lower()}.{function}"


def normalize_physical_pci_bdf(value: str) -> str:
    match = re.search(_PCI_BDF_PATTERN_TEXT, value)
    if match is None:
        return ""
    function = match.group("function") or "0"
    address = f"{match.group('bus').lower()}:{match.group('slot').lower()}.{function}"
    domain = match.group("domain")
    return f"{domain.lower()}:{address}" if domain is not None else address


def normalize_observed_full_pci_bdf(value: str) -> str:
    match = re.fullmatch(_OBSERVED_FULL_PCI_BDF_PATTERN_TEXT, value)
    if match is None:
        return ""
    domain = int(match.group("domain"), 16)
    return f"{domain:08x}:{match.group('address').lower()}"


def observed_pci_bdf_components(value: str) -> tuple[int | None, int, int, int | None] | None:
    match = re.fullmatch(_OBSERVED_PCI_BDF_PATTERN_TEXT, value)
    if match is None:
        return None
    domain, function = match.group("domain"), match.group("function")
    return (
        int(domain, 16) if domain is not None else None,
        int(match.group("bus"), 16),
        int(match.group("device"), 16),
        int(function, 16) if function is not None else None,
    )


def observed_pci_bdf_conflicts(first: str, second: str) -> bool:
    first_components = observed_pci_bdf_components(first)
    second_components = observed_pci_bdf_components(second)
    if first_components is None or second_components is None:
        return False
    return any(
        left is not None and right is not None and left != right
        for left, right in zip(first_components, second_components, strict=True)
    )


def normalize_windows_pnp_instance_id(value: str) -> str:
    canonical = value.upper()
    if (
        not value.isascii()
        or len(canonical) > 255
        or not re.fullmatch(
            r"PCI\\VEN_[0-9A-F]{4}&DEV_[0-9A-F]{4}(?:&[A-Z0-9_]+)*\\[A-Z0-9&_.-]+",
            canonical,
        )
    ):
        return ""
    return canonical
