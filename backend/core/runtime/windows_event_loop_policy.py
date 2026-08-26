"""SoAI - Windows asyncio event loop policy configuration [backend/core/runtime/windows_event_loop_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    from asyncio.windows_events import WindowsProactorEventLoopPolicy

__all__ = ("configure_windows_event_loop_policy",)


def configure_windows_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
