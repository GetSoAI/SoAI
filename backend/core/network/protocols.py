"""SoAI - Core network protocol contracts [backend/core/network/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.types.json import JSONValue

__all__ = ("HTTPJsonResponseProtocol",)


class HTTPJsonResponseProtocol(Protocol):
    def json(self) -> JSONValue: ...
