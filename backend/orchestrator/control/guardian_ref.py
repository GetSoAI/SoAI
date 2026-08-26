"""SoAI - Mutable orchestrator guardian reference [backend/orchestrator/control/guardian_ref.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.plugins.protocols_guardian import PluginGuardianProtocol

__all__ = ("GuardianRef",)


class GuardianRef:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value: PluginGuardianProtocol | None = None
