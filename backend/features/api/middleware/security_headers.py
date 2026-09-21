"""SoAI - API security headers middleware [backend/features/api/middleware/security_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.runtime.proxy_headers import (
    normalize_scheme_value,
    parse_forwarded_proto,
    parse_x_forwarded_proto,
)
from core.runtime.trusted_proxy import is_trusted_proxy_client_host
from core.validation.string_sequences import normalize_string_sequence

__all__ = ("SecurityHeadersMiddleware",)

HSTS_MAX_AGE_SECONDS = 31_536_000
ROBOTS_POLICY = "noindex, nofollow, nosnippet, noimageindex"


class SecurityHeadersMiddleware:

    class ConfigState:
        __slots__ = (
            "hsts_enabled",
            "insecure_policy",
            "permissions_policy",
            "secure_policy",
        )

        def __init__(self) -> None:
            self.hsts_enabled = False
            self.secure_policy = ""
            self.insecure_policy = ""
            self.permissions_policy = ""

    DEFAULT_CSP_DIRECTIVES: tuple[str, ...] = (
        "default-src 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self'",
        "style-src 'self' blob:",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "worker-src 'self' blob:",
        "manifest-src 'self'",
    )
    DEFAULT_PERMISSIONS_POLICY = (
        "camera=(self), microphone=(self), geolocation=(), clipboard-write=(self)"
    )

    def __init__(
        self,
        app: ASGIApp,
        *,
        config_state: ConfigState | None = None,
        hsts_enabled: bool = False,
        content_security_policy: str | Iterable[str] | None = None,
        permissions_policy: str | None = None,
        upgrade_insecure_requests: bool = False,
    ) -> None:
        self.app = app
        if config_state is None:
            config_state = self.configure_state(
                None,
                hsts_enabled=hsts_enabled,
                content_security_policy=content_security_policy,
                permissions_policy=permissions_policy,
                upgrade_insecure_requests=upgrade_insecure_requests,
            )
        self._config_state = config_state

    @classmethod
    def _resolve_scheme(cls, scope: Scope, headers: Headers) -> str:
        app = scope.get("app")
        client = scope.get("client")
        client_host = (
            client[0] if isinstance(client, tuple) and isinstance(client[0], str) else None
        )
        if is_trusted_proxy_client_host(app, client_host):
            forwarded_proto = parse_x_forwarded_proto(headers.get("x-forwarded-proto"))
            if forwarded_proto:
                return forwarded_proto
            forwarded = parse_forwarded_proto(headers.get("forwarded"))
            if forwarded:
                return forwarded
        scope_scheme = normalize_scheme_value(scope.get("scheme"))
        if scope_scheme:
            return scope_scheme
        return "http"

    @classmethod
    def _build_csp_policy(cls, policy_definition: str | Iterable[str] | None) -> str:
        if policy_definition is None:
            directives = cls.DEFAULT_CSP_DIRECTIVES
        elif isinstance(policy_definition, str):
            directives = tuple(
                part.strip() for part in policy_definition.split(";") if part.strip()
            )
        else:
            directives = tuple(
                part.strip() for part in policy_definition if isinstance(part, str) and part.strip()
            )
        unique = normalize_string_sequence(directives)
        return "; ".join(unique)

    @staticmethod
    def _without_upgrade_directive(policy: str) -> str:
        if not policy:
            return ""
        directives = [part.strip() for part in policy.split(";") if part.strip()]
        filtered = [
            directive
            for directive in directives
            if directive.lower() != "upgrade-insecure-requests"
        ]
        return "; ".join(normalize_string_sequence(filtered))

    @staticmethod
    def _ensure_upgrade_directive(policy: str) -> str:
        directives = [part.strip() for part in policy.split(";") if part.strip()]
        if not directives:
            directives = []
        if all(directive.lower() != "upgrade-insecure-requests" for directive in directives):
            directives.append("upgrade-insecure-requests")
        return "; ".join(normalize_string_sequence(directives))

    @classmethod
    def _normalize_permissions_policy(cls, policy_definition: str | None) -> str:
        if isinstance(policy_definition, str):
            candidate = policy_definition.strip()
            if candidate:
                return candidate
        return cls.DEFAULT_PERMISSIONS_POLICY

    @classmethod
    def configure_state(
        cls,
        state: ConfigState | None,
        *,
        hsts_enabled: bool = False,
        content_security_policy: str | Iterable[str] | None = None,
        permissions_policy: str | None = None,
        upgrade_insecure_requests: bool = False,
    ) -> ConfigState:
        if state is None:
            state = cls.ConfigState()
        secure_policy = cls._build_csp_policy(content_security_policy)
        if upgrade_insecure_requests:
            secure_policy = cls._ensure_upgrade_directive(secure_policy)
        state.hsts_enabled = bool(hsts_enabled)
        state.secure_policy = secure_policy
        state.insecure_policy = cls._without_upgrade_directive(secure_policy)
        state.permissions_policy = cls._normalize_permissions_policy(permissions_policy)
        return state

    @staticmethod
    def _ensure_header(headers: MutableHeaders, name: str, value: str) -> None:
        if headers.get(name) is None:
            headers[name] = value

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(raw=scope.get("headers") or [])
        scheme = self._resolve_scheme(scope, headers)
        setter = self._ensure_header

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                setter(response_headers, "X-Content-Type-Options", "nosniff")
                setter(response_headers, "X-Robots-Tag", ROBOTS_POLICY)
                setter(response_headers, "Referrer-Policy", "same-origin")
                setter(response_headers, "X-Frame-Options", "DENY")
                setter(response_headers, "Cross-Origin-Resource-Policy", "same-origin")
                setter(
                    response_headers,
                    "Permissions-Policy",
                    self._config_state.permissions_policy,
                )
                if response_headers.get("Content-Security-Policy") is None:
                    policy = (
                        self._config_state.secure_policy
                        if scheme == "https"
                        else self._config_state.insecure_policy
                    )
                    if policy:
                        response_headers["Content-Security-Policy"] = policy
                if self._config_state.hsts_enabled and scheme == "https":
                    response_headers["Strict-Transport-Security"] = (
                        f"max-age={HSTS_MAX_AGE_SECONDS}; includeSubDomains"
                    )
                elif "Strict-Transport-Security" in response_headers:
                    del response_headers["Strict-Transport-Security"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
