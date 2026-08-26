"""SoAI - API key repository dependencies [backend/database/repositories/users/api_keys/service_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.di.validation import require_dependencies

__all__ = ("DatabaseAPIKeysDependencies",)


@dataclass(frozen=True, slots=True)
class DatabaseAPIKeysDependencies:
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    fernet: tuple[Fernet, ...]
    configured_key_count: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseAPIKeysDependencies",
            config=self.config,
            configured_key_count=self.configured_key_count,
            core=self.core,
            fernet=self.fernet,
        )
