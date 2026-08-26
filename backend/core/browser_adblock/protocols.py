"""SoAI - Shared browser adblock protocols [backend/core/browser_adblock/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.browser_adblock.matcher import EasyListMatchResult

__all__ = ("EasyListAdblockServiceProtocol",)


class EasyListAdblockServiceProtocol(Protocol):
    @property
    def next_refresh_unix(self) -> float: ...

    @property
    def source_name(self) -> str: ...

    def match(
        self,
        request_url: str,
        *,
        request_host: str | None,
        request_type: str | None,
        document_host: str | None,
        is_third_party: bool | None,
    ) -> EasyListMatchResult: ...

    async def refresh_from_remote(self) -> None: ...
