"""SoAI - Dependency injection protocols [backend/core/di/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import Field
from typing import ClassVar, Never, Protocol

__all__ = ("DependenciesDataclassProtocol", "DependencyValueProtocol")


class DependenciesDataclassProtocol(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Never]]]


class DependencyValueProtocol(Protocol):
    __slots__ = ()
