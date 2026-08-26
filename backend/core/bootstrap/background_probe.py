"""SoAI - Background launcher readiness probes [backend/core/bootstrap/background_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.bootstrap.discovery_ports import DISCOVERY_PORTS
from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.system_api.route_paths import SOAI_SYSTEM_HEALTH_PATH
from core.validation.coercion import coerce_int_from_numberish

if TYPE_CHECKING:
    from core.runtime.api_endpoint import RuntimeApiEndpoint
    from core.types.json import JSONValue

__all__ = (
    "DiscoveryProbeResult",
    "check_api_health",
    "probe_discovery",
    "resolve_runtime_endpoint_probe",
)

DISCOVERY_PROBE_TIMEOUT_SECONDS: float = 2.0
HEALTH_CHECK_PATH: str = SOAI_SYSTEM_HEALTH_PATH
PROBE_RESPONSE_LIMIT_BYTES: int = 65536
PROBE_READ_CHUNK_BYTES: int = 4096


@dataclass(frozen=True, slots=True)
class DiscoveryProbeResult:
    scheme: str
    port: int
    host: str
    ca_file: str | None = None


def resolve_runtime_endpoint_probe(
    runtime_api_endpoint: RuntimeApiEndpoint,
    *,
    ca_file: str | None = None,
) -> DiscoveryProbeResult:
    scheme, host, port = runtime_api_endpoint.local_connection_coordinates()
    return DiscoveryProbeResult(
        scheme=scheme,
        port=port,
        host=host,
        ca_file=ca_file,
    )


@dataclass(frozen=True, slots=True)
class ProbeHttpResponse:
    status: int
    body: bytes


def _coerce_discovery_port(value: JSONValue, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    parsed = coerce_int_from_numberish(value)
    if parsed is None:
        return fallback
    if parsed < 1 or parsed > 65535:
        return fallback
    return parsed


def _build_probe_request(path: str) -> bytes:
    if not path.startswith("/") or "\r" in path or "\n" in path:
        raise ValueError("Invalid probe path")
    request = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
    return request.encode("ascii")


def _build_probe_tls_context() -> ssl.SSLContext:
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE
    return tls_context


def _parse_probe_response(payload: bytes) -> ProbeHttpResponse | None:
    headers, separator, body = payload.partition(b"\r\n\r\n")
    if not separator:
        return None
    status_line, line_separator, _remaining_headers = headers.partition(b"\r\n")
    if not line_separator:
        return None
    status_parts = status_line.decode("iso-8859-1").split(" ", 2)
    if len(status_parts) < 2:
        return None
    status = coerce_int_from_numberish(status_parts[1])
    if status is None or status < 100 or status > 599:
        return None
    return ProbeHttpResponse(status=status, body=body)


def _exchange_probe_request(
    connection: socket.socket | ssl.SSLSocket,
    path: str,
) -> ProbeHttpResponse | None:
    connection.settimeout(DISCOVERY_PROBE_TIMEOUT_SECONDS)
    connection.sendall(_build_probe_request(path))
    chunks: list[bytes] = []
    received_bytes = 0
    while received_bytes < PROBE_RESPONSE_LIMIT_BYTES:
        chunk = connection.recv(PROBE_READ_CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
        received_bytes += len(chunk)
    if not chunks:
        return None
    return _parse_probe_response(b"".join(chunks))


def _open_probe_response(
    port: int,
    *,
    use_tls: bool,
    path: str,
) -> ProbeHttpResponse | None:
    response: ProbeHttpResponse | None = None
    connection: socket.socket | ssl.SSLSocket = socket.create_connection(
        ("127.0.0.1", port),
        timeout=DISCOVERY_PROBE_TIMEOUT_SECONDS,
    )
    try:
        if use_tls:
            connection = _build_probe_tls_context().wrap_socket(
                connection,
                server_hostname="127.0.0.1",
            )
        response = _exchange_probe_request(connection, path)
    finally:
        connection.close()
    return response


def _probe_discovery_port(port: int, *, use_tls: bool) -> DiscoveryProbeResult | None:
    result: DiscoveryProbeResult | None = None
    try:
        response = _open_probe_response(port, use_tls=use_tls, path="/")
        if response is None:
            return None
        if response.status != 200:
            return None
        data = parse_json_dict(response.body, field="discovery probe")
        scheme = str(data.get("scheme", "http")).strip().lower()
        if scheme not in {"http", "https"}:
            return None
        real_port = _coerce_discovery_port(data.get("port", port), fallback=port)
        result = DiscoveryProbeResult(scheme=scheme, port=real_port, host="127.0.0.1")
    except (
        OSError,
        ValueError,
        ValidationError,
        ssl.SSLError,
    ):
        result = None
    return result


def probe_discovery() -> DiscoveryProbeResult | None:
    for port in DISCOVERY_PORTS:
        for use_tls in (False, True):
            result = _probe_discovery_port(port, use_tls=use_tls)
            if result is not None:
                return result
    return None


def check_api_health(discovery: DiscoveryProbeResult) -> bool:
    use_tls = discovery.scheme == "https"
    is_healthy = False
    try:
        response = _open_probe_response(
            discovery.port,
            use_tls=use_tls,
            path=HEALTH_CHECK_PATH,
        )
        if response is None:
            return False
        is_healthy = response.status == 200
    except (OSError, ValueError, ssl.SSLError):
        is_healthy = False
    return is_healthy
