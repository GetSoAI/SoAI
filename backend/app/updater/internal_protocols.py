"""SoAI - App updater internal protocols [backend/app/updater/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginUpdateServiceProtocol",
    "SoftwareUpdateServiceProtocol",
    "UpdaterApiClientProtocol",
)


class UpdaterApiClientProtocol(Protocol):
    def get_base_url_and_auth_headers(
        self,
        *,
        timeout: float,
    ) -> tuple[str, dict[str, str], ssl.SSLContext | None]: ...

    def make_api_request(
        self,
        *,
        method: str,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        body: JSONDict | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> JSONDict | None: ...


class SoftwareUpdateServiceProtocol(Protocol):
    def get_software_update_status(
        self,
    ) -> tuple[JSONDict, JSONDict] | None: ...

    def run_software_update_check(self) -> int: ...

    def run_software_update(self) -> int: ...


class PluginUpdateServiceProtocol(Protocol):
    def run_plugin_update(self) -> int: ...

    def run_plugin_update_check(self) -> int: ...
