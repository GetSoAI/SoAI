"""SoAI - Canonical agent turn scope values [backend/core/agent/turn_scope_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "TURN_SCOPE_ALL",
    "TURN_SCOPE_ROOT",
    "TURN_SCOPE_SUBAGENT",
)

TURN_SCOPE_ROOT = "root"
TURN_SCOPE_SUBAGENT = "subagent"
TURN_SCOPE_ALL: tuple[str, ...] = (TURN_SCOPE_ROOT, TURN_SCOPE_SUBAGENT)
