"""SoAI - Durable initial-setup state [backend/core/users/bootstrap_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = ("BootstrapState",)


class BootstrapState(str, Enum):
    UNINITIALIZED = "uninitialized"
    COMPLETE = "complete"
    INTEGRITY_ERROR = "integrity_error"
