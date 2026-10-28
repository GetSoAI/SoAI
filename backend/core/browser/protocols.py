"""SoAI - Browser session ownership contracts [backend/core/browser/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("PlaywrightScopeTaskProtocol",)


class PlaywrightScopeTaskProtocol(Protocol):
    def done(self) -> bool: ...
