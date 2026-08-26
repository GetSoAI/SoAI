"""SoAI - Discovery server TLS socket wrapping [backend/app/lifecycle/discovery_tls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl

from app.lifecycle.discovery_http_server import DiscoveryHTTPServer
from core.errors.exceptions import ValidationError
from core.security.tls_policy import apply_server_tls_policy

__all__ = ("apply_discovery_transport_layer_security",)


def apply_discovery_transport_layer_security(
    server: DiscoveryHTTPServer,
    transport_layer_security_options: dict[str, str | int] | None,
) -> None:
    if not transport_layer_security_options:
        return
    certfile_value = transport_layer_security_options.get("ssl_certfile")
    keyfile_value = transport_layer_security_options.get("ssl_keyfile")
    password_value = transport_layer_security_options.get("ssl_keyfile_password")
    if not isinstance(certfile_value, str) or not certfile_value.strip():
        raise ValidationError("Discovery HTTPS requires ssl_certfile.")
    if not isinstance(keyfile_value, str) or not keyfile_value.strip():
        raise ValidationError("Discovery HTTPS requires ssl_keyfile.")
    password = password_value if isinstance(password_value, str) else None
    context = apply_server_tls_policy(ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER))
    context.load_cert_chain(
        certfile=certfile_value,
        keyfile=keyfile_value,
        password=password,
    )
    server.set_transport_layer_security_context(context)
