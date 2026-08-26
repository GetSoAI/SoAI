"""SoAI - Core OS updates types [backend/core/os/updates_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.timing.epoch import epoch_ms

__all__ = (
    "InstalledPackage",
    "UpdateHistoryEntry",
    "UpdatesCheckResult",
    "UpdatesStatusSnapshot",
    "UpgradablePackage",
)


@dataclass(frozen=True, slots=True)
class UpgradablePackage:
    name: str
    current_version: str | None
    new_version: str | None
    is_security: bool
    download_size: int = 0


@dataclass(frozen=True, slots=True)
class UpdatesCheckResult:
    packages: tuple[UpgradablePackage, ...]
    checked_at_ms: int = field(default_factory=epoch_ms)


@dataclass(frozen=True, slots=True)
class UpdatesStatusSnapshot:
    available_updates_count: int
    security_updates_count: int
    last_check_at_ms: int | None
    reboot_required: bool
    timestamp_ms: int = field(default_factory=epoch_ms)


@dataclass(frozen=True, slots=True)
class InstalledPackage:
    name: str
    version: str
    architecture: str | None


@dataclass(frozen=True, slots=True)
class UpdateHistoryEntry:
    start_date: str | None
    end_date: str | None
    commandline: str | None
    installed: tuple[str, ...]
    upgraded: tuple[str, ...]
    removed: tuple[str, ...]
