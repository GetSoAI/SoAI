"""SoAI - Callback identity description for event bus logging [backend/core/events/bus_callback_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable

from core.events.types_base import Event

__all__ = ("describe_callback",)


def describe_callback(callback: Callable[[Event], Awaitable[None]]) -> str:
    if isinstance(callback, functools.partial):
        target = callback.func
        suffix = "[partial]"
    else:
        target = callback
        suffix = ""
    try:
        module = target.__module__
    except AttributeError:
        module = None
    try:
        qualname = target.__qualname__
    except AttributeError:
        qualname = None
    if not qualname:
        try:
            qualname = target.__name__
        except AttributeError:
            qualname = None
    if module and qualname:
        return f"{module}.{qualname}{suffix}"
    if qualname:
        return f"{qualname}{suffix}"
    return f"{target!r}{suffix}"
