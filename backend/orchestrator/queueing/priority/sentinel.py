"""SoAI - Shutdown sentinel for worker termination signaling [backend/orchestrator/queueing/priority/sentinel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

__all__ = ("ShutdownSentinel",)


class ShutdownSentinel:
    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return "<ShutdownSentinel>"
