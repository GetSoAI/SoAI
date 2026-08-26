"""SoAI - Plugin loopback listener process helpers [backend/plugin_sdk/contracts/loopback_listener_processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.loopback_listener_identity import (
    LoopbackListenerIdentity,
    LoopbackListenerResolution,
    resolve_verified_loopback_listener_identity,
)
from core.runtime.process_identity_termination import terminate_process_matching_identity

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "LoopbackListenerIdentity",
    "LoopbackListenerResolution",
    "resolve_verified_loopback_listener_identity",
    "terminate_verified_loopback_listener",
)


async def terminate_verified_loopback_listener(
    identity: LoopbackListenerIdentity,
    *,
    plugin_name: str,
    logger: LoggerProtocol,
    graceful_timeout_sec: float = 10.0,
    force_timeout_sec: float = 10.0,
) -> bool:
    result = await terminate_process_matching_identity(
        identity.pid,
        identity.create_time_ms,
        plugin_name,
        logger,
        graceful_timeout_sec=graceful_timeout_sec,
        force_timeout_sec=force_timeout_sec,
    )
    return result.terminated
