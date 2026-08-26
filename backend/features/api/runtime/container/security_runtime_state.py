"""SoAI - Security runtime state container [backend/features/api/runtime/container/security_runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SecurityRuntimeState",)


class SecurityRuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proxy_headers_enabled: bool = False
        self._trusted_proxy_networks: tuple[str, ...] = ()
        self._https_redirect_active: bool = False
        self._hsts_enabled: bool = False
        self._content_security_policy: str = ""
        self._content_security_policy_insecure: str = ""

    def configure(
        self,
        *,
        proxy_headers_enabled: bool,
        trusted_proxy_networks: tuple[str, ...],
        https_redirect_active: bool,
        hsts_enabled: bool,
        content_security_policy: str,
        content_security_policy_insecure: str,
    ) -> None:
        with self._lock:
            self._proxy_headers_enabled = bool(proxy_headers_enabled)
            self._trusted_proxy_networks = tuple(trusted_proxy_networks)
            self._https_redirect_active = bool(https_redirect_active)
            self._hsts_enabled = bool(hsts_enabled)
            self._content_security_policy = str(content_security_policy or "")
            self._content_security_policy_insecure = str(content_security_policy_insecure or "")

    def snapshot(self) -> JSONDict:
        with self._lock:
            return {
                "proxy_headers_enabled": self._proxy_headers_enabled,
                "trusted_proxy_networks": list(self._trusted_proxy_networks),
                "https_redirect_active": self._https_redirect_active,
                "hsts_enabled": self._hsts_enabled,
                "content_security_policy": self._content_security_policy,
                "content_security_policy_insecure": self._content_security_policy_insecure,
            }
