"""SoAI - Config lock acquisition and lock-path utilities [backend/core/config/locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "get_lock_path",
    "resolve_lock_directory",
)


class ConfigLockTimeout(ConfigurationError):

    def __init__(self, message: str, *, config_path: str | None = None) -> None:
        super().__init__(
            message,
            details={"config_path": config_path} if config_path else {},
            operation="config.lock_acquisition",
        )

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.message,), {"config_path": (self.details or {}).get("config_path")})


def resolve_lock_directory(path: str | None) -> str | None:
    if not path:
        return None
    resolved = os.path.abspath(path)
    os.makedirs(resolved, exist_ok=True)
    return resolved


def get_lock_path(path: str, *, lock_directory: str | None) -> str:
    if lock_directory:
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        return os.path.join(lock_directory, f"{digest}.lock")
    return f"{path}.lock"
