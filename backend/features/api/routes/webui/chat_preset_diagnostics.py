"""SoAI - Rate-limited chat preset integrity diagnostics [backend/features/api/routes/webui/chat_preset_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict

from core.logging.trace import get_logger

__all__ = ("ChatPresetIntegrityDiagnostics",)

_DIAGNOSTIC_INTERVAL_SECONDS = 60.0
_DIAGNOSTIC_USER_LIMIT = 256
LOGGER_NAME = "SoAI.features.api.chat_preset_diagnostics"


class ChatPresetIntegrityDiagnostics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._times: OrderedDict[tuple[int, int], float] = OrderedDict()
        self._logger = get_logger(LOGGER_NAME)

    def log(self, *, user_id: int, invalid_count: int, trace_id: str | None) -> None:
        if invalid_count <= 0:
            return
        now = time.monotonic()
        diagnostic_key = (user_id, invalid_count)
        with self._lock:
            previous = self._times.get(diagnostic_key)
            if previous is not None and now - previous < _DIAGNOSTIC_INTERVAL_SECONDS:
                return
            self._times[diagnostic_key] = now
            self._times.move_to_end(diagnostic_key)
            while len(self._times) > _DIAGNOSTIC_USER_LIMIT:
                self._times.popitem(last=False)
        self._logger.log(
            logging.ERROR,
            "Chat preset library contains structurally invalid records.",
            extra={
                "operation": "chat_presets.list",
                "trace_id": trace_id,
                "user_id": user_id,
                "structurally_invalid_count": invalid_count,
            },
        )
