"""SoAI - Canonical plugin stop outcome typing [backend/core/orchestrator/stop_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("PluginStopOutcome",)


@dataclass(frozen=True, slots=True)
class PluginStopOutcome:
    terminated: bool
    message: str = ""
