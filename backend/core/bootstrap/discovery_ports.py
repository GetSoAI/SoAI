"""SoAI - Shared discovery port definitions [backend/core/bootstrap/discovery_ports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

DISCOVERY_PORT_START: int = 7950
DISCOVERY_PORT_STOP: int = 7960
DISCOVERY_PORTS: tuple[int, ...] = (
    7950,
    7951,
    7952,
    7953,
    7954,
    7955,
    7956,
    7957,
    7958,
    7959,
    7960,
)

__all__ = (
    "DISCOVERY_PORTS",
    "DISCOVERY_PORT_START",
    "DISCOVERY_PORT_STOP",
)
