"""SoAI - Dependency injection protocols [backend/core/di/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("DependencyValueProtocol",)


class DependencyValueProtocol(Protocol):
    __slots__ = ()
