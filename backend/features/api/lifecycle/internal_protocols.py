"""SoAI - Internal protocols for API lifecycle management [backend/features/api/lifecycle/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("SecurityRuntimeStateProtocol",)


class SecurityRuntimeStateProtocol(Protocol):
    def configure(
        self,
        *,
        proxy_headers_enabled: bool,
        trusted_proxy_networks: tuple[str, ...],
        https_redirect_active: bool,
        hsts_enabled: bool,
        content_security_policy: str,
        content_security_policy_insecure: str,
    ) -> None: ...
