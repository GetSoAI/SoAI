"""SoAI - Subprocess termination primitives [backend/core/process/termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import admit_bounded_blocking_call
from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.process.group_exit_observation import OwnedGroupExitObservation
from core.process.group_exit_observation_probe import observe_owned_process_group_isolated
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, MODERATE_DELAY_SEC, RESPONSIVE_TIMEOUT_SEC
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "poll_process_exit_without_reaping",
    "terminate_subprocess_gracefully",
    "terminate_process_and_wait",
    "confirm_owned_process_group_exit",
)


def _signal_process(
    process: asyncio.subprocess.Process,
    *,
    force: bool,
) -> bool:
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except ProcessLookupError:
        return False
    return True


async def terminate_subprocess_gracefully(
    process: asyncio.subprocess.Process | ManagedProcess,
    *,
    graceful_timeout_sec: float = float(RESPONSIVE_TIMEOUT_SEC),
    logger: LoggerProtocol,
    operation: str,
    process_group: bool = False,
    deadline: MonotonicDeadline | None = None,
    pool: BoundedBlockingPool | None = None,
) -> None:
    if process_group:
        if not isinstance(process, subprocess.Popen):
            raise ProcessError("Async process groups require owned unreaped managed authority.")
        await _terminate_managed_group(
            process,
            graceful_timeout_sec=graceful_timeout_sec,
            operation=operation,
            deadline=deadline,
            pool=pool,
        )
        return
    if isinstance(process, subprocess.Popen):
        raise ProcessError("Managed async cleanup requires its owned process group.")
    try:
        _signal_process(process, force=False)
        try:
            await asyncio.wait_for(process.wait(), timeout=graceful_timeout_sec)
        except TimeoutError:
            _signal_process(process, force=True)
            await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
    except RECOVERABLE_EXCEPTIONS as termination_error:
        log_exception(
            logger,
            termination_error,
            message="Error during subprocess termination",
            operation=operation,
            level="warning",
        )
        raise ProcessError(
            "Subprocess termination failed.",
            operation=operation,
            cause=termination_error,
        ) from termination_error


async def _terminate_managed_group(
    process: ManagedProcess,
    *,
    graceful_timeout_sec: float,
    operation: str,
    deadline: MonotonicDeadline | None,
    pool: BoundedBlockingPool | None,
) -> None:
    def terminate_owned() -> None:
        terminate_process_and_wait(
            process, timeout_sec=graceful_timeout_sec, process_group=True, deadline=deadline
        )

    try:
        termination_task = (
            create_ephemeral_task(
                asyncio.to_thread(terminate_owned),
                name="core.process.owned-group-cleanup",
                log_exceptions=False,
            )
            if pool is None
            else await admit_bounded_blocking_call(pool, terminate_owned, deadline=deadline)
        )
        try:
            await asyncio.shield(termination_task)
        finally:
            await wait_for_task_completion(termination_task, retain_resources_until_complete=True)
            termination_task.result()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        raise ProcessGroupCleanupError(
            "Owned subprocess group exit remains unverified.",
            process=process,
            operation=operation,
            cause=exception,
        ) from exception


def poll_process_exit_without_reaping(process: ManagedProcess) -> int | None:
    if os.name == "nt":
        return process.poll()
    if process.returncode is not None:
        return process.returncode
    status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if status is None:
        return None
    return status.si_status if status.si_code == os.CLD_EXITED else -status.si_status


def _terminate_process_group_and_wait(
    process: ManagedProcess, *, timeout_sec: float, deadline: MonotonicDeadline | None
) -> None:
    _require_unreaped_process_group(process)
    observation = OwnedGroupExitObservation.UNVERIFIED
    for requested_signal in (signal.SIGTERM, signal.SIGKILL):
        os.killpg(process.pid, requested_signal)
        phase_timeout = (
            timeout_sec if deadline is None else min(timeout_sec, deadline.remaining_seconds())
        )
        observation = _observe_until_terminal(process, deadline_after(phase_timeout), timeout_sec)
        if observation == OwnedGroupExitObservation.TERMINAL:
            process.wait(timeout=timeout_sec)
            return
    if observation == OwnedGroupExitObservation.UNVERIFIED:
        observation = _observe_until_terminal(
            process, deadline if deadline is not None else deadline_after(timeout_sec), timeout_sec
        )
        if observation == OwnedGroupExitObservation.TERMINAL:
            process.wait(timeout=timeout_sec)
            return
    raise ProcessError(
        "Process group cleanup did not verify exit before its deadline.",
        details={"group_observation": observation.value},
    )


def _observe_until_terminal(
    process: ManagedProcess, phase_deadline: MonotonicDeadline, timeout_sec: float
) -> OwnedGroupExitObservation:
    while True:
        observation = observe_owned_process_group_isolated(process.pid, deadline=phase_deadline)
        if observation == OwnedGroupExitObservation.TERMINAL or phase_deadline.expired():
            return observation
        sleep_seconds(
            min(MODERATE_DELAY_SEC, timeout_sec / 2, phase_deadline.remaining_seconds() / 2)
        )


def _require_unreaped_process_group(process: ManagedProcess) -> None:
    if os.name == "nt" or process.returncode is not None:
        raise ProcessError("Process group cleanup requires an unreaped POSIX child.")
    poll_process_exit_without_reaping(process)
    if os.getpgid(process.pid) != process.pid:
        raise ProcessError("Process group cleanup requires its owned group leader.")


def confirm_owned_process_group_exit(process: ManagedProcess, *, timeout_sec: float) -> bool:
    _require_unreaped_process_group(process)
    if poll_process_exit_without_reaping(process) is None:
        return False
    deadline = deadline_after(timeout_sec)
    if deadline.expired():
        return False
    if observe_owned_process_group_isolated(process.pid, deadline=deadline) != (
        OwnedGroupExitObservation.TERMINAL
    ):
        return False
    process.wait(timeout=timeout_sec)
    return True


def terminate_process_and_wait(
    process: ManagedProcess,
    *,
    timeout_sec: float,
    process_group: bool = False,
    deadline: MonotonicDeadline | None = None,
) -> None:
    if process_group:
        _terminate_process_group_and_wait(process, timeout_sec=timeout_sec, deadline=deadline)
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout_sec)
