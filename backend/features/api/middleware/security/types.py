"""SoAI - API security types [backend/features/api/middleware/security/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ProxyHeaderAnomalyTracker",)


class ProxyHeaderAnomalyTracker:
    __slots__ = ("alert", "lock")

    def __init__(self, alert: JSONDict | None = None) -> None:
        self.lock = threading.Lock()
        self.alert = alert
