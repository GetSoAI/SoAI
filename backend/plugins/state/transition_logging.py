"""SoAI - Plugin state transition logging helpers [backend/plugins/state/transition_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("log_skipped_same_state_transition",)


def log_skipped_same_state_transition(
    logger: LoggerProtocol,
    plugin_name: str,
    previous_state: str,
    new_state: str,
) -> None:
    logger.debug(
        "Skipping same-state transition for '%s': %s → %s",
        plugin_name,
        previous_state,
        new_state,
    )
