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

__all__ = (
    "flush_process_replacement_output",
    "redirect_standard_streams_to_devnull",
    "replace_current_process",
)


def flush_process_replacement_output() -> None:
    for output_stream in (sys.stdout, sys.stderr):
        try:
            output_stream.flush()
        except BrokenPipeError:
            continue


def redirect_standard_streams_to_devnull() -> None:
    read_descriptor = os.open(os.devnull, os.O_RDONLY)
    try:
        write_descriptor = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(read_descriptor, 0)
            os.dup2(write_descriptor, 1)
            os.dup2(write_descriptor, 2)
        finally:
            if write_descriptor not in (0, 1, 2):
                os.close(write_descriptor)
    finally:
        if read_descriptor not in (0, 1, 2):
            os.close(read_descriptor)


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
