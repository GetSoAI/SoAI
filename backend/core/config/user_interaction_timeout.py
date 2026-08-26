"""SoAI - Server-owned interactive user timeout configuration [backend/core/config/user_interaction_timeout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.numeric_lenient import coerce_lenient_positive_int
from core.config.protocols import ConfigProtocol

__all__ = (
    "DEFAULT_USER_INTERACTION_TIMEOUT_MS",
    "USER_INTERACTION_TIMEOUT_CONFIG_KEY",
    "resolve_user_interaction_timeout_ms",
)

USER_INTERACTION_TIMEOUT_CONFIG_KEY = "TOOLS.MCP.ELICITATION.WAIT_TIMEOUT_MS"
DEFAULT_USER_INTERACTION_TIMEOUT_MS = 3_600_000


def resolve_user_interaction_timeout_ms(config: ConfigProtocol) -> int:
    return coerce_lenient_positive_int(
        config.get(USER_INTERACTION_TIMEOUT_CONFIG_KEY),
        default=DEFAULT_USER_INTERACTION_TIMEOUT_MS,
        minimum=1,
    )
