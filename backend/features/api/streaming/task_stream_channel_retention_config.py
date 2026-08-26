"""SoAI - Task stream retention config helpers [backend/features/api/streaming/task_stream_channel_retention_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol

__all__ = ("resolve_post_terminal_retention_seconds",)

_DEFAULT_POST_TERMINAL_RETENTION_SEC = 300.0


def resolve_post_terminal_retention_seconds(config: ConfigProtocol) -> float:
    try:
        configured = float(
            config.get_float("SERVER.HTTP.STREAMING.POST_TERMINAL_CHANNEL_RETENTION_SEC"),
        )
    except (AttributeError, TypeError, ValueError):
        configured = _DEFAULT_POST_TERMINAL_RETENTION_SEC
    return max(0.0, configured)
