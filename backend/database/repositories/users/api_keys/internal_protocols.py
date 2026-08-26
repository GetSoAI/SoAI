"""SoAI - Internal protocols for API key repository helpers [backend/database/repositories/users/api_keys/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from database.repositories.users.bearer_token_hash_crypto import BearerTokenHashCryptor

__all__ = ("DatabaseAPIKeysServiceProtocol",)


class DatabaseAPIKeysServiceProtocol(Protocol):
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    cryptor: BearerTokenHashCryptor
