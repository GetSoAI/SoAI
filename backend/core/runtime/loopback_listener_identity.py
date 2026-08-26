"""SoAI - Loopback listener process identity resolution [backend/core/runtime/loopback_listener_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.logging.protocols import LoggerProtocol

__all__ = (
    "LoopbackListenerIdentity",
    "LoopbackListenerResolution",
    "resolve_verified_loopback_listener_process_identity",
    "resolve_verified_loopback_listener_identity",
)


@dataclass(frozen=True, slots=True)
class LoopbackListenerIdentity:
    pid: int
    create_time_ms: int
    command_line: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LoopbackListenerResolution:
    identity: LoopbackListenerIdentity | None
    listener_found: bool
    ownership_verified: bool
    reason: str


def resolve_verified_loopback_listener_identity(
    *,
    host: str,
    port: int,
    expected_command_parts: Sequence[str],
    logger: LoggerProtocol,
) -> LoopbackListenerResolution:
    normalized_host = host.strip()
    if not _is_loopback_host(normalized_host):
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Host '{host}' is not loopback.",
        )
    if port <= 0:
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Invalid listener port '{port}'.",
        )
    normalized_expected = tuple(part for part in expected_command_parts if part)
    if not normalized_expected:
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason="No expected command identity parts were provided.",
        )
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.Error as exception:
        logger.warning(
            "Failed to inspect TCP listeners: %s",
            f"{type(exception).__name__}: {exception}",
        )
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Failed to inspect TCP listeners: {type(exception).__name__}.",
        )
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN:
            continue
        local_address = connection.laddr
        if len(local_address) < 2:
            continue
        listener_host = str(local_address[0])
        listener_port = int(local_address[1])
        if listener_port != port or not _listener_host_matches(normalized_host, listener_host):
            continue
        pid = connection.pid
        if pid is None or pid <= 0:
            return LoopbackListenerResolution(
                identity=None,
                listener_found=True,
                ownership_verified=False,
                reason=f"Listener on {host}:{port} has no resolvable process id.",
            )
        return _resolve_process_identity(
            pid=pid,
            host=host,
            port=port,
            expected_command_parts=normalized_expected,
        )
    return LoopbackListenerResolution(
        identity=None,
        listener_found=False,
        ownership_verified=False,
        reason=f"No loopback listener found on {host}:{port}.",
    )


def _resolve_process_identity(
    *,
    pid: int,
    host: str,
    port: int,
    expected_command_parts: tuple[str, ...],
) -> LoopbackListenerResolution:
    try:
        process = psutil.Process(pid)
        command_line = tuple(process.cmdline())
        create_time_ms = int(process.create_time() * 1000.0)
    except psutil.NoSuchProcess:
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Listener process {pid} on {host}:{port} exited during inspection.",
        )
    except psutil.AccessDenied:
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Access denied while inspecting listener process {pid} on {host}:{port}.",
        )
    if not _command_contains_expected_parts(command_line, expected_command_parts):
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Listener process {pid} on {host}:{port} is not the expected worker.",
        )
    return LoopbackListenerResolution(
        identity=LoopbackListenerIdentity(
            pid=pid,
            create_time_ms=create_time_ms,
            command_line=command_line,
        ),
        listener_found=True,
        ownership_verified=True,
        reason="OK",
    )


def resolve_verified_loopback_listener_process_identity(
    *,
    pid: int,
    host: str,
    port: int,
    expected_command_parts: tuple[str, ...],
) -> LoopbackListenerResolution:
    resolution = _resolve_process_identity(
        pid=pid,
        host=host,
        port=port,
        expected_command_parts=expected_command_parts,
    )
    identity = resolution.identity
    if not resolution.ownership_verified or identity is None:
        return resolution
    try:
        process = psutil.Process(pid)
        if int(process.create_time() * 1000.0) != identity.create_time_ms:
            return LoopbackListenerResolution(
                identity=None,
                listener_found=True,
                ownership_verified=False,
                reason=f"Listener process {pid} identity changed during inspection.",
            )
        connections = process.net_connections(kind="tcp")
    except psutil.Error as exception:
        return LoopbackListenerResolution(
            identity=None,
            listener_found=True,
            ownership_verified=False,
            reason=f"Failed to inspect listener process {pid}: {type(exception).__name__}.",
        )
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or len(connection.laddr) < 2:
            continue
        listener_host = str(connection.laddr[0])
        listener_port = int(connection.laddr[1])
        if listener_port == port and _listener_host_matches(host, listener_host):
            return resolution
    return LoopbackListenerResolution(
        identity=None,
        listener_found=False,
        ownership_verified=False,
        reason=f"Process {pid} is not listening on {host}:{port}.",
    )


def _command_contains_expected_parts(
    command_line: tuple[str, ...],
    expected_command_parts: tuple[str, ...],
) -> bool:
    if not command_line:
        return False
    return all(part in command_line for part in expected_command_parts)


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _listener_host_matches(expected_host: str, listener_host: str) -> bool:
    if expected_host == "localhost":
        return _is_loopback_host(listener_host)
    try:
        expected_address = ipaddress.ip_address(expected_host)
        listener_address = ipaddress.ip_address(listener_host)
    except ValueError:
        return expected_host == listener_host
    if isinstance(expected_address, ipaddress.IPv6Address):
        expected_address = expected_address.ipv4_mapped or expected_address
    if isinstance(listener_address, ipaddress.IPv6Address):
        listener_address = listener_address.ipv4_mapped or listener_address
    return expected_address == listener_address
