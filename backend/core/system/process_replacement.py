"""SoAI - Current-process replacement helpers [backend/core/system/process_replacement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.system.process_launcher import spawn_managed_process

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess

__all__ = ("flush_process_replacement_output", "replace_current_process")


def flush_process_replacement_output() -> None:
    for output_stream in (sys.stdout, sys.stderr):
        try:
            output_stream.flush()
        except BrokenPipeError:
            continue


def replace_current_process(command: Sequence[str]) -> int:
    argv = list(command)
    if not argv:
        raise ValueError("replace_current_process requires a non-empty command.")
    if os.name != "nt":
        os.execv(argv[0], argv)
        return 0
    process_handle = spawn_managed_process(argv)
    with process_handle:
        return _wait_for_console_shared_child(process_handle)


def _wait_for_console_shared_child(process_handle: ManagedProcess) -> int:
    while True:
        try:
            return int(process_handle.wait())
        except KeyboardInterrupt:
            continue
