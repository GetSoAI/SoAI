"""SoAI - Port discovery handler factory [backend/app/lifecycle/port_discovery_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import html
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from ipaddress import ip_address
from typing import override

from app.lifecycle.discovery_validation import resolve_discovery_cors_origin
from core.licensing.types import Edition
from core.logging.trace import get_logger
from core.meta.instance_identity import InstanceIdentity, build_instance_identity_payload
from core.runtime.api_endpoint import RuntimeApiEndpoint
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict

__all__ = (
    "PortDiscoveryHandler",
    "build_port_discovery_handler",
)

LOGGER_NAME = "SoAI.app.lifecycle.port_discovery_handler"


def _is_tls_client_hello(request_line: bytes) -> bool:
    if len(request_line) < 6 or request_line[0] != 0x16 or request_line[1] != 0x03:
        return False
    record_length = int.from_bytes(request_line[3:5], "big")
    return (
        0x01 <= request_line[2] <= 0x04 and 0 < record_length <= 16384 and request_line[5] == 0x01
    )


class PortDiscoveryHandler(BaseHTTPRequestHandler):
    main_api_port: int = 5090
    preferred_api_port: int = 5090
    main_api_scheme: str = "http"
    edition: Edition = "soai-core"
    instance_identity: InstanceIdentity = InstanceIdentity(instance_id="", instance_name=None)
    close_connection: bool = False
    raw_requestline: bytes = b""

    @override
    def version_string(self) -> str:
        return "SoAI"

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        runtime_api_endpoint = RuntimeApiEndpoint(
            bind_host="127.0.0.1",
            scheme=str(self.main_api_scheme),
            preferred_port=int(self.preferred_api_port),
            effective_port=int(self.main_api_port),
        )
        response_payload: JSONDict = runtime_api_endpoint.to_public_payload()
        response_payload["status"] = "ok"
        response_payload["edition"] = self.edition
        identity_payload = filter_json_mapping_strict(
            build_instance_identity_payload(self.instance_identity),
            error_message="Instance identity payload must be JSON-compatible.",
        )
        response_payload.update(identity_payload)
        response_bytes = serialize_json_compact_stable_strict(response_payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Connection", "close")
        headers = self.headers
        cors_origin = resolve_discovery_cors_origin(
            headers.get("origin"),
            host_header=headers.get("host"),
        )
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        try:
            self.wfile.write(response_bytes)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        self.close_connection = True

    @override
    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        return

    @override
    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        if code != HTTPStatus.BAD_REQUEST or not self._is_loopback_tls_client_hello():
            super().send_error(code, message, explain)
            return
        get_logger(LOGGER_NAME).debug(
            "Probable TLS ClientHello sent to plaintext discovery listener from loopback peer."
        )
        short_message, long_message = self.responses[code]
        reason = short_message if message is None else message
        body = (
            self.error_message_format
            % {
                "code": code,
                "message": html.escape(reason, quote=False),
                "explain": html.escape(long_message if explain is None else explain, quote=False),
            }
        ).encode("UTF-8", "replace")
        self.send_response(code, reason)
        self.send_header("Connection", "close")
        self.send_header("Content-Type", self.error_content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _is_loopback_tls_client_hello(self) -> bool:
        try:
            loopback_peer = ip_address(self.client_address[0]).is_loopback
        except ValueError:
            loopback_peer = False
        return loopback_peer and _is_tls_client_hello(self.raw_requestline)


def build_port_discovery_handler(
    *,
    main_api_port: int,
    preferred_api_port: int,
    main_api_scheme: str,
    edition: Edition,
    instance_identity: InstanceIdentity,
) -> type[PortDiscoveryHandler]:
    configured_main_api_port = int(main_api_port)
    configured_preferred_api_port = int(preferred_api_port)
    configured_main_api_scheme = str(main_api_scheme)
    configured_edition = edition
    configured_instance_identity = instance_identity

    class _ConfiguredPortDiscoveryHandler(PortDiscoveryHandler):
        main_api_port = configured_main_api_port
        preferred_api_port = configured_preferred_api_port
        main_api_scheme = configured_main_api_scheme
        edition = configured_edition
        instance_identity = configured_instance_identity

    return _ConfiguredPortDiscoveryHandler
