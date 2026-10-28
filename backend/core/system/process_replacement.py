"""SoAI - Current-process replacement helpers [backend/core/system/process_replacement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import select
import stat
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.filesystem.descriptor_io import open_descriptor
from core.system.process_launcher import spawn_managed_process

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "flush_process_replacement_output",
    "redirect_unusable_standard_streams_to_devnull",
    "replace_current_process",
)

_STANDARD_INPUT_DESCRIPTOR = 0
_STANDARD_DESCRIPTORS = (0, 1, 2)


def flush_process_replacement_output() -> None:
    for output_stream in (sys.stdout, sys.stderr):
        if output_stream is None:
            continue
        try:
            output_stream.flush()
        except (OSError, ValueError):
            continue


def redirect_unusable_standard_streams_to_devnull() -> None:
    for descriptor in _STANDARD_DESCRIPTORS:
        if not _standard_stream_is_usable(descriptor):
            _redirect_descriptor_to_devnull(descriptor)


def _standard_stream_is_usable(descriptor: int) -> bool:
    try:
        mode = os.fstat(descriptor).st_mode
    except OSError as exception:
        if exception.errno == errno.EBADF:
            return False
        raise
    if descriptor == _STANDARD_INPUT_DESCRIPTOR:
        return True
    if not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)):
        return True
    return _output_channel_has_reader(descriptor)


def _output_channel_has_reader(descriptor: int) -> bool:
    poller = select.poll()
    poller.register(descriptor, select.POLLOUT)
    disconnected_events = select.POLLERR | select.POLLHUP | select.POLLNVAL
    return not any(events & disconnected_events for _descriptor, events in poller.poll(0))


def _redirect_descriptor_to_devnull(descriptor: int) -> None:
    flags = os.O_RDONLY if descriptor == _STANDARD_INPUT_DESCRIPTOR else os.O_WRONLY
    devnull_descriptor = open_descriptor(os.devnull, flags)
    if devnull_descriptor == descriptor:
        os.set_inheritable(descriptor, True)
        return
    try:
        os.dup2(devnull_descriptor, descriptor)
    finally:
        os.close(devnull_descriptor)


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
