"""SoAI - Formatting-related protocols [backend/core/formatting/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("FormatBytesCallable",)


class FormatBytesCallable(Protocol):
    def __call__(self, size_bytes: float) -> str: ...
