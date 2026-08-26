"""SoAI - MCP access token repository internal protocols [backend/database/repositories/users/mcp_access_tokens/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.protocols import DatabaseCoreProtocol
from database.repositories.users.bearer_token_hash_crypto import BearerTokenHashCryptor

__all__ = ("DatabaseMcpAccessTokensServiceProtocol",)


class DatabaseMcpAccessTokensServiceProtocol(Protocol):
    core: DatabaseCoreProtocol
    cryptor: BearerTokenHashCryptor
