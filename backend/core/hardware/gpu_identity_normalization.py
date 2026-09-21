"""SoAI - GPU identity normalization [backend/core/hardware/gpu_identity_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = (
    "normalize_identity_name",
    "normalize_model_key",
    "normalize_pci_bdf",
    "normalize_physical_pci_bdf",
)

_IDENTITY_SEPARATOR_PATTERN_TEXT = r"[^a-z0-9]+"
_PCI_BDF_PATTERN_TEXT = (
    r"(?:(?P<domain>[0-9a-fA-F]{4}):)?"
    r"(?P<bus>[0-9a-fA-F]{2}):"
    r"(?P<slot>[0-9a-fA-F]{2})"
    r"(?:\.(?P<function>[0-7]))?"
)


def normalize_identity_name(value: str) -> str:
    return re.sub(_IDENTITY_SEPARATOR_PATTERN_TEXT, "", value.lower())


def normalize_model_key(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = re.sub(_IDENTITY_SEPARATOR_PATTERN_TEXT, "-", name.lower()).strip("-")
    return normalized or None


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
