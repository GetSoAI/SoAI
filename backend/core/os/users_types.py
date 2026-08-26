"""SoAI - Core OS user sync types [backend/core/os/users_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.timing.epoch import epoch_ms

__all__ = (
    "SystemUserInfo",
    "UserSyncStatusSnapshot",
)


@dataclass(frozen=True, slots=True)
class SystemUserInfo:
    webui_user_id: int
    linux_username: str
    exists: bool
    uid: int | None
    gid: int | None
    home_dir: str | None
    shell: str | None
    locked: bool | None
    groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UserSyncStatusSnapshot:
    enabled: bool
    timestamp_ms: int = field(default_factory=epoch_ms)
