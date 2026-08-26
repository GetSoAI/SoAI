"""SoAI - PTY session validation and trace logging [backend/terminal/session_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.trace_logging import TRACE_LEVEL

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from terminal.session_registry import PTYSessionStore
    from terminal.types import PTYSession

__all__ = (
    "log_terminal_trace",
    "require_live_session",
)


def require_live_session(registry: PTYSessionStore, session_id: str) -> PTYSession:
    session = registry.get(session_id)
    if session is None or session.closed:
        raise ValidationError(f"Session {session_id} not found or closed.")
    return session


def log_terminal_trace(logger: TraceLogger, message: str) -> None:
    logger.log(TRACE_LEVEL, message)
