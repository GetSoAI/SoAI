"""SoAI - Best-effort local TCP port ownership diagnostics [backend/core/network/port_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import psutil

__all__ = ("PortOwnerDiagnostic", "resolve_tcp_port_owners")


@dataclass(frozen=True, slots=True)
class PortOwnerDiagnostic:
    pid: int
    process_name: str


def resolve_tcp_port_owners(port: int) -> tuple[PortOwnerDiagnostic, ...]:
    owners: dict[int, PortOwnerDiagnostic] = {}
    try:
        connections = psutil.net_connections("inet")
    except psutil.Error:
        return ()
    for connection in connections:
        if not connection.laddr or connection.laddr.port != port:
            continue
        if connection.status != psutil.CONN_LISTEN or connection.pid is None:
            continue
        try:
            process_name = psutil.Process(connection.pid).name().strip()
        except psutil.Error:
            process_name = ""
        owners[connection.pid] = PortOwnerDiagnostic(
            pid=connection.pid,
            process_name=process_name or "unavailable",
        )
    return tuple(owners[pid] for pid in sorted(owners))
