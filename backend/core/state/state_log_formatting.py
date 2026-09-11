"""SoAI - Formatting helpers for state transitions in logs [backend/core/state/state_log_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError
from core.logging.formatter_support import ANSI_CODE_PATTERN, ANSI_RESET
from core.logging.palette import (
    ANSI_ASH,
    ANSI_BLUE,
    ANSI_CHARCOAL,
    ANSI_GRAPHITE,
    ANSI_GREEN,
    ANSI_GREY,
    ANSI_ORANGE,
    ANSI_PEWTER,
    ANSI_PLATINUM,
    ANSI_RED,
    ANSI_SKY,
    ANSI_VERDANT,
    ANSI_WHITE,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_IDLE,
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    ORCH_STATE_UNKNOWN,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_REMOVING_BACKEND,
    PLUGIN_STATE_STOPPED,
    PLUGIN_STATE_UPDATE_ERROR,
    resolve_plugin_runtime_state_name,
)

__all__ = (
    "format_state_for_log",
    "format_state_tokens_for_log",
    "format_state_transition_for_log",
)

_STATE_LOG_RESET = ANSI_RESET


def _state_log_arrow() -> str:
    return f"{ANSI_WHITE}->{_STATE_LOG_RESET}"


def format_state_for_log(state: str) -> str:
    match state:
        case value if value == ORCH_STATE_UNKNOWN:
            color = ANSI_GREY
        case value if value == ORCH_STATE_STOPPED:
            color = ANSI_ASH
        case value if value == ORCH_STATE_STARTING:
            color = ANSI_SKY
        case value if value == ORCH_STATE_LOADING:
            color = ANSI_BLUE
        case value if value == ORCH_STATE_IDLE:
            color = ANSI_GREEN
        case value if value == ORCH_STATE_READY_PENDING_DISPATCH:
            color = ANSI_BLUE
        case value if value == ORCH_STATE_READY:
            color = ANSI_VERDANT
        case value if value == ORCH_STATE_READY_DIRTY:
            color = ANSI_GREEN
        case value if value == ORCH_STATE_PROCESSING:
            color = ANSI_ORANGE
        case value if value == ORCH_STATE_STOPPING:
            color = ANSI_ORANGE
        case value if value == ORCH_STATE_ERROR:
            color = ANSI_RED
        case value if value == ORCH_STATE_QUARANTINED:
            color = ANSI_RED
        case value if value == ORCH_STATE_DISABLED:
            color = ANSI_PLATINUM
        case value if value == PLUGIN_STATE_NOT_DETECTED:
            color = ANSI_CHARCOAL
        case value if value == PLUGIN_STATE_BACKEND_NOT_INSTALLED:
            color = ANSI_GRAPHITE
        case value if value == PLUGIN_STATE_BACKEND_INSTALLING:
            color = ANSI_ORANGE
        case value if value == PLUGIN_STATE_BACKEND_UPDATING:
            color = ANSI_ORANGE
        case value if value == PLUGIN_STATE_STOPPED:
            color = ANSI_PEWTER
        case value if value == PLUGIN_STATE_REMOVING_BACKEND:
            color = ANSI_ORANGE
        case value if value == PLUGIN_STATE_DELETING:
            color = ANSI_ORANGE
        case value if value == PLUGIN_STATE_INSTALL_ERROR:
            color = ANSI_RED
        case value if value == PLUGIN_STATE_LOAD_ERROR:
            color = ANSI_RED
        case value if value == PLUGIN_STATE_UPDATE_ERROR:
            color = ANSI_RED
        case value if value == PLUGIN_STATE_BACKEND_UNINSTALL_ERROR:
            color = ANSI_RED
        case value if value == PLUGIN_STATE_DELETE_ERROR:
            color = ANSI_RED
        case value if value == PLUGIN_STATE_PERSISTENT_READY:
            color = ANSI_GREEN
        case value if value == PLUGIN_STATE_ABSENT:
            color = ANSI_GREY
        case value if value == PLUGIN_STATE_INCOMPATIBLE:
            color = ANSI_RED
        case _:
            raise ValidationError(f"Unknown state '{state}' for log formatting.")
    return f"{color}{state}{_STATE_LOG_RESET}"


def format_state_transition_for_log(previous_state: str, new_state: str) -> str:
    previous_state_label = format_state_for_log(previous_state)
    new_state_label = format_state_for_log(new_state)
    return f"{previous_state_label} {_state_log_arrow()} {new_state_label}"


def format_state_tokens_for_log(message: str) -> str:
    def _format_token(match: re.Match[str]) -> str:
        state = resolve_plugin_runtime_state_name(match.group(1))
        return format_state_for_log(state) if state is not None else match.group(0)

    return re.sub(
        rf"(?<!\w)(?:{ANSI_CODE_PATTERN})*([A-Z][A-Z_]*)(?:{re.escape(ANSI_RESET)})?(?!\w)",
        _format_token,
        message,
    )
