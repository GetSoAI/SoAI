"""SoAI - Instance control API reachability probes [backend/app/cli/instance_control_probes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
import ssl
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from ipaddress import ip_address

from core.network.ip import is_local_network_ip

__all__ = (
    "probe_api_health",
    "probe_api_reachable",
)


def probe_api_reachable(host: str, port: int) -> bool:
    try:
        probe_port = _resolve_probe_port(port)
        connect_host = _resolve_local_probe_host(host)
        with socket.create_connection((connect_host or host, probe_port), timeout=0.5):
            return True
    except (OSError, OverflowError, TypeError, ValueError):
        return False


def probe_api_health(
    host: str,
    port: int,
    scheme: str,
    health_path: str,
    *,
    ca_file: str | None = None,
) -> bool:
    connection: HTTPConnection | None = None
    try:
        probe_port = _resolve_probe_port(port)
        scheme_normalized = scheme.strip().lower()
        if scheme_normalized not in {"http", "https"}:
            return False
        connect_host = _resolve_local_probe_host(host)
        target_host = connect_host or host
        if scheme_normalized == "https":
            connection = _open_https_connection(target_host, probe_port, ca_file)
        else:
            connection = HTTPConnection(target_host, probe_port, timeout=2.0)
        connection.request("GET", health_path)
        response = connection.getresponse()
        response.read()
        return response.status == 200
    except (AttributeError, HTTPException, OSError, OverflowError, TypeError, ValueError):
        return False
    finally:
        if connection is not None:
            connection.close()


def _open_https_connection(
    target_host: str,
    port: int,
    ca_file: str | None,
) -> HTTPConnection:
    tls_context = ssl.create_default_context(cafile=ca_file)
    connection_type: type[HTTPSConnection] = HTTPSConnection
    return connection_type(target_host, port, timeout=2.0, context=tls_context)


def _resolve_local_probe_host(host: str) -> str | None:
    normalized = str(host or "").strip().lower()
    if normalized in {"localhost", "localhost."}:
        return None
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if "%" in normalized:
        normalized = normalized.split("%", maxsplit=1)[0]
    address = ip_address(normalized)
    if not is_local_network_ip(address):
        raise ValueError(f"Instance control probe target is not local: {host}")
    return normalized


def _resolve_probe_port(port: int) -> int:
    if isinstance(port, bool):
        raise ValueError("Instance control probe port must be an integer.")
    try:
        normalized = int(port)
    except (OverflowError, TypeError, ValueError) as exception:
        raise ValueError(f"Instance control probe port is invalid: {port}") from exception
    if normalized < 1 or normalized > 65535:
        raise ValueError(f"Instance control probe port is invalid: {port}")
    return normalized
