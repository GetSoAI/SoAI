"""SoAI - Immutable optional plugin artwork contract [backend/core/plugins/logo_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = (
    "LOGO_FILENAMES",
    "MAX_LOGO_DIMENSION",
    "MAX_LOGO_OUTPUT_BYTES",
    "MAX_LOGO_SOURCE_BYTES",
    "InvalidPluginLogo",
    "PluginLogoResult",
    "PluginLogoSource",
)

LOGO_FILENAMES: tuple[str, ...] = ("logo.png", "logo.webp")
MAX_LOGO_SOURCE_BYTES = 1_048_576
MAX_LOGO_DIMENSION = 512
MAX_LOGO_OUTPUT_BYTES = 2_097_152


@dataclass(frozen=True, slots=True)
class PluginLogoSource:
    filename: str | None = None
    content: bytes = b""
    rejection: str | None = None


@dataclass(frozen=True, slots=True)
class PluginLogoResult:
    status: Literal["available", "absent", "invalid"]
    content: bytes = b""
    reason: str | None = None
    width: int = 0
    height: int = 0


class InvalidPluginLogo(ValueError):
    __slots__ = ()
