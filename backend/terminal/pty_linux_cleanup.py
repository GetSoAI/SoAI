"""SoAI - Linux PTY process cleanup [backend/terminal/pty_linux_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import signal

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from core.timing.sleep import sleep_seconds

__all__ = ("close_pty",)

LOGGER_NAME = "SoAI.terminal.pty_linux_cleanup"
OPERATION_REAP_SESSION_LEADER = "pty_linux_cleanup.close_pty.reap_session_leader"
OPERATION_SIGHUP_SESSION = "pty_linux_cleanup.close_pty.sighup_session"
OPERATION_SIGKILL_SESSION = "pty_linux_cleanup.close_pty.sigkill_session"
OPERATION_SIGTERM_SESSION = "pty_linux_cleanup.close_pty.sigterm_session"


def _collect_session_pids(session_id: int) -> set[int]:
    session_pids: set[int] = set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        candidate_pid = int(entry)
        try:
            if os.getsid(candidate_pid) == session_id:
                session_pids.add(candidate_pid)
        except (ProcessLookupError, FileNotFoundError):
            continue
        except PermissionError:
            continue
    return session_pids


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _send_signal_to_session_pids(
    session_pids: set[int],
    signal_value: signal.Signals,
    *,
    logger: TraceLogger,
    pid: int,
    operation: str,
    message: str,
) -> OSError | None:
    first_failure: OSError | None = None
    for session_pid in session_pids:
        try:
            os.kill(session_pid, signal_value)
        except ProcessLookupError:
            continue
        except PermissionError as exception:
            if first_failure is None:
                first_failure = exception
            log_exception(
                logger,
                exception,
                message=message,
                operation=operation,
                details={"pid": pid, "session_pid": session_pid},
            )
    return first_failure


def _raise_cleanup_failure(exception: OSError | StateError | None, *, pid: int) -> None:
    if exception is None:
        return
    raise StateError(
        "PTY resources could not be fully closed.",
        operation="terminal.pty_linux_cleanup.close_pty",
        details={"pid": pid},
    ) from exception


def close_pty(master_fd: int, pid: int) -> None:
    logger = get_logger(LOGGER_NAME)
    cleanup_failure: OSError | StateError | None = None
    try:
        os.close(master_fd)
    except OSError as exception:
        if exception.errno != errno.EBADF:
            cleanup_failure = exception
    session_id = pid
    session_pids = _collect_session_pids(session_id)
    session_pids.add(pid)
    signal_failure = _send_signal_to_session_pids(
        session_pids,
        signal.SIGHUP,
        logger=logger,
        pid=pid,
        operation=OPERATION_SIGHUP_SESSION,
        message="Failed to send SIGHUP to PTY session process during shutdown.",
    )
    if cleanup_failure is None:
        cleanup_failure = signal_failure
    signal_failure = _send_signal_to_session_pids(
        session_pids,
        signal.SIGTERM,
        logger=logger,
        pid=pid,
        operation=OPERATION_SIGTERM_SESSION,
        message="Failed to send SIGTERM to PTY session process during shutdown.",
    )
    if cleanup_failure is None:
        cleanup_failure = signal_failure

    leader_reaped = False
    for _ in range(40):
        if not leader_reaped:
            try:
                waited_pid, _ = os.waitpid(pid, os.WNOHANG)
                if waited_pid == pid:
                    leader_reaped = True
            except (ChildProcessError, ProcessLookupError):
                leader_reaped = True
        remaining = _collect_session_pids(session_id)
        if not remaining and (leader_reaped or not _is_pid_alive(pid)):
            _raise_cleanup_failure(cleanup_failure, pid=pid)
            return
        sleep_seconds(SHORT_POLL_INTERVAL_SEC)

    remaining = _collect_session_pids(session_id)
    if not leader_reaped and _is_pid_alive(pid):
        remaining.add(pid)
    signal_failure = _send_signal_to_session_pids(
        remaining,
        signal.SIGKILL,
        logger=logger,
        pid=pid,
        operation=OPERATION_SIGKILL_SESSION,
        message="Failed to send SIGKILL to PTY session process during shutdown.",
    )
    if cleanup_failure is None:
        cleanup_failure = signal_failure

    deadline = deadline_after(2.0)
    while not deadline.expired():
        if not _is_pid_alive(pid):
            break
        sleep_seconds(SHORT_POLL_INTERVAL_SEC)
    try:
        if not leader_reaped:
            waited_pid, _ = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                leader_reaped = True
    except ChildProcessError:
        leader_reaped = True
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to reap PTY session leader after shutdown.",
            operation=OPERATION_REAP_SESSION_LEADER,
            details={"pid": pid},
        )
        if cleanup_failure is None:
            cleanup_failure = exception
    if _collect_session_pids(session_id) or (not leader_reaped and _is_pid_alive(pid)):
        if cleanup_failure is None:
            cleanup_failure = StateError(
                "PTY session remained alive after forced shutdown.",
                operation="terminal.pty_linux_cleanup.close_pty",
                details={"pid": pid},
            )
    _raise_cleanup_failure(cleanup_failure, pid=pid)
