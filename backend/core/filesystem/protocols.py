"""SoAI - Filesystem hashing cancellation protocols [backend/core/filesystem/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("CancellableHashCalculationProtocol",)


class CancellableHashCalculationProtocol(Protocol):
    def __call__(self, path: str, /, *, cancellation_check: Callable[[], None]) -> str | None: ...
