"""SoAI - Core OS SSH types [backend/core/os/ssh_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.timing.epoch import epoch_ms

__all__ = ("SshStatus",)


@dataclass(frozen=True, slots=True)
class SshStatus:
    service_name: str
    active: bool
    enabled: bool
    active_state: str | None
    enabled_state: str | None
    timestamp_ms: int = field(default_factory=epoch_ms)
