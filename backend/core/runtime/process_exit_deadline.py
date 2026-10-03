"""SoAI - Process-owned shutdown and finalization deadlines [backend/core/runtime/process_exit_deadline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading
from types import TracebackType
from typing import Literal

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exceptions import StateError, ValidationError
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC
from core.validation.strict_numbers import require_finite_float_strict

__all__ = ("ProcessExitDeadline",)


class ProcessExitDeadline:
    def __init__(self) -> None:
        self._owner_pid = os.getpid()
        self._condition = threading.Condition()
        self._deadline: MonotonicDeadline | None = None
        self._phase: Literal["inactive", "graceful", "finalizing", "expired", "closed"] = "inactive"
        self._thread: threading.Thread | None = None

    def __enter__(self) -> ProcessExitDeadline:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def phase(self) -> str:
        with self._condition:
            return self._phase

    def begin_shutdown(self, timeout_sec: float) -> None:
        self._arm(timeout_sec, phase="graceful")

    def begin_finalization(self, timeout_sec: float | None = None) -> None:
        timeout = INTERACTIVE_TIMEOUT_SEC if timeout_sec is None else timeout_sec
        self._arm(timeout, phase="finalizing")

    def _arm(self, timeout_sec: float, *, phase: Literal["graceful", "finalizing"]) -> None:
        timeout = require_finite_float_strict(
            timeout_sec, error_message="Process exit deadline requires a finite positive timeout."
        )
        if timeout <= 0:
            raise ValidationError("Process exit deadline requires a finite positive timeout.")
        if os.getpid() != self._owner_pid:
            raise StateError("Process exit deadline belongs to another process.")
        with self._condition:
            if self._phase == "closed":
                raise StateError("Process exit deadline is closed.")
            if self._phase == "expired":
                return
            if self._deadline is not None and self._deadline.expired():
                self._phase = "expired"
                self._condition.notify_all()
                return
            if self._phase in (phase, "finalizing"):
                return
            self._deadline = deadline_after(timeout)
            self._phase = phase
            if self._thread is None:
                try:
                    deadline_thread = threading.Thread(
                        target=self._wait_for_exit_deadline,
                        name="soai-process-exit-deadline",
                        daemon=True,
                    )
                    deadline_thread.start()
                except (RuntimeError, OSError) as exception:
                    self._deadline = None
                    self._phase = "inactive"
                    raise StateError("Process exit deadline could not start.") from exception
                self._thread = deadline_thread
            self._condition.notify_all()

    def _wait_for_exit_deadline(self) -> None:
        with self._condition:
            while self._phase != "closed":
                if self._deadline is None:
                    raise StateError("An armed process exit deadline is missing.")
                remaining = self._deadline.remaining_seconds()
                if remaining <= 0:
                    self._phase = "expired"
                    break
                self._condition.wait(timeout=min(remaining, threading.TIMEOUT_MAX))
            if self._phase == "closed":
                return
        if os.getpid() == self._owner_pid:
            os._exit(1)

    def close(self) -> None:
        with self._condition:
            if self._phase != "closed" and self._deadline is not None and self._deadline.expired():
                self._phase = "expired"
            if self._phase != "expired":
                self._phase = "closed"
            self._condition.notify_all()
            deadline_thread = self._thread
        if deadline_thread is not None:
            deadline_thread.join(timeout=LOCAL_IO_TIMEOUT_SEC)
            if deadline_thread.is_alive():
                raise StateError("Process exit deadline thread did not stop within its deadline.")
