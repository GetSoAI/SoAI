"""SoAI - Task TTL sentinel and typing [backend/core/tasks/ttl.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type TTLMillis = int | None | type[TTLUseDefault]

__all__ = ("TTLUseDefault",)


@dataclass(frozen=True, slots=True)
class TTLUseDefault: ...
