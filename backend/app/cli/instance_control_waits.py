"""SoAI - CLI instance restart and shutdown wait operations [backend/app/cli/instance_control_waits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

import psutil

from app.cli.instance_control_discovery import (
    DiscoveryProbeResult,
    probe_discovery,
    probe_discovery_api_health,
    probe_discovery_api_reachable,
)
from app.cli.instance_control_pid import read_running_pid, resolve_pid_file_path
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exceptions import ValidationError
from core.runtime.instance_record import (
    canonicalize_runtime_base_dir,
    read_runtime_instance_record,
)
from core.timing.sleep import sleep_seconds

__all__ = (
    "is_process_running",
    "read_runtime_id",
    "wait_for_api_health_up",
    "wait_for_api_transition_down",
    "wait_for_pid_change",
    "wait_for_process_exit",
    "wait_for_restart",
    "wait_for_stop_api_down",
)

PROCESS_POLL_INTERVAL_SECONDS = 0.1
RESTART_POLL_INTERVAL_SECONDS = 0.02
RESTART_INITIAL_DELAY_SECONDS = 10.0
DISCOVERY_WAIT_INTERVAL_SECONDS = 1.0


def wait_for_process_exit(pid: int, timeout_seconds: float) -> bool:
    deadline = deadline_after(timeout_seconds)
    while True:
        try:
            process = psutil.Process(pid)
            status: str | None
            try:
                status = process.status()
            except psutil.Error:
                status = None
            if status == psutil.STATUS_ZOMBIE:
                return True
            if not process.is_running():
                return True
        except psutil.NoSuchProcess:
            return True
        except psutil.Error:
            process = None
        if deadline.expired():
            return False
        sleep_seconds(PROCESS_POLL_INTERVAL_SECONDS)


def is_process_running(pid: int) -> bool:
    try:
        process = psutil.Process(pid)
        status: str | None
        try:
            status = process.status()
        except psutil.Error:
            status = None
        if status == psutil.STATUS_ZOMBIE:
            return False
        return process.is_running()
    except psutil.NoSuchProcess:
        return False
    except psutil.Error:
        return True


def wait_for_pid_change(
    base_dir: str,
    logger: logging.Logger,
    *,
    prior_pid: int,
    deadline: MonotonicDeadline,
    initial_runtime_id: str | None = None,
    expected_edition: str,
) -> bool:
    observed_running_pid = False
    observed_pid_file_gap = False
    expected_runtime_id = initial_runtime_id or read_runtime_id(
        base_dir,
        logger,
        expected_edition=expected_edition,
    )
    while not deadline.expired():
        current_pid = read_running_pid(
            base_dir,
            logger,
            expected_edition=expected_edition,
        )
        if current_pid is not None:
            observed_running_pid = True
        if observed_running_pid and current_pid is not None and current_pid != prior_pid:
            return True
        if observed_running_pid and current_pid is None:
            observed_pid_file_gap = True
        if observed_pid_file_gap and current_pid is not None:
            return True
        current_runtime_id = read_runtime_id(
            base_dir,
            logger,
            expected_edition=expected_edition,
        )
        if expected_runtime_id is not None and (
            current_runtime_id is not None and current_runtime_id != expected_runtime_id
        ):
            return True
        sleep_seconds(RESTART_POLL_INTERVAL_SECONDS)
    return False


def wait_for_api_transition_down(
    discovery_info: DiscoveryProbeResult,
    *,
    deadline: MonotonicDeadline,
) -> bool:
    observed_up = True
    consecutive_down = 0
    while not deadline.expired():
        is_reachable = probe_discovery_api_reachable(discovery_info)
        if is_reachable:
            observed_up = True
            consecutive_down = 0
        elif observed_up:
            consecutive_down += 1
            if consecutive_down >= 2:
                return True
        sleep_seconds(RESTART_POLL_INTERVAL_SECONDS)
    return False


def read_runtime_id(
    base_dir: str,
    logger: logging.Logger,
    *,
    expected_edition: str,
) -> str | None:
    try:
        pid_file_path = resolve_pid_file_path(base_dir, logger)
        record = read_runtime_instance_record(pid_file_path)
        if record.base_dir != canonicalize_runtime_base_dir(base_dir):
            return None
        if record.edition != expected_edition:
            return None
        return record.runtime_id
    except (OSError, ValidationError):
        return None


def wait_for_api_health_up(
    base_dir: str,
    *,
    expected_edition: str,
    timeout_seconds: float,
) -> DiscoveryProbeResult | None:
    deadline = deadline_after(timeout_seconds)
    while True:
        discovery_info = probe_discovery(base_dir, expected_edition=expected_edition)
        if discovery_info is not None and probe_discovery_api_health(discovery_info):
            return discovery_info
        if deadline.expired():
            return None
        sleep_seconds(DISCOVERY_WAIT_INTERVAL_SECONDS)


def wait_for_restart(
    base_dir: str,
    logger: logging.Logger,
    *,
    pid: int,
    timeout_seconds: float,
    initial_runtime_id: str | None = None,
    expected_edition: str,
) -> bool:
    deadline = deadline_after(timeout_seconds)
    baseline_discovery = probe_discovery(base_dir, expected_edition=expected_edition)
    if baseline_discovery is None:
        logger.warning(
            "Failed to resolve SoAI discovery endpoint before restart. Falling back to PID transition detection (PID %s).",
            pid,
        )
        if not wait_for_pid_change(
            base_dir,
            logger,
            prior_pid=pid,
            deadline=deadline,
            initial_runtime_id=initial_runtime_id,
            expected_edition=expected_edition,
        ):
            return False
    elif probe_discovery_api_reachable(baseline_discovery):
        if not wait_for_api_transition_down(baseline_discovery, deadline=deadline):
            return False
    else:
        logger.warning(
            "SoAI discovery endpoint was known but not reachable before restart. Falling back to PID transition detection (PID %s).",
            pid,
        )
        if not wait_for_pid_change(
            base_dir,
            logger,
            prior_pid=pid,
            deadline=deadline,
            initial_runtime_id=initial_runtime_id,
            expected_edition=expected_edition,
        ):
            return False

    logger.info(
        "SoAI endpoint is down after restart request. Waiting %s seconds before checking if it comes back online...",
        int(RESTART_INITIAL_DELAY_SECONDS),
    )
    sleep_seconds(RESTART_INITIAL_DELAY_SECONDS)

    discovery_info = wait_for_api_health_up(
        base_dir,
        expected_edition=expected_edition,
        timeout_seconds=deadline.remaining_seconds(),
    )
    if discovery_info is None:
        return False
    logger.info(
        "SoAI discovery endpoint is up after a restart (%s://%s:%s).",
        discovery_info.scheme,
        discovery_info.host,
        discovery_info.port,
    )
    return True


def wait_for_stop_api_down(
    base_dir: str,
    *,
    expected_edition: str,
    pid: int,
    timeout_seconds: float,
) -> bool:
    deadline = deadline_after(timeout_seconds)
    baseline_discovery: DiscoveryProbeResult | None = probe_discovery(
        base_dir,
        expected_edition=expected_edition,
    )
    consecutive_down = 0
    while True:
        if not is_process_running(pid):
            return True
        if baseline_discovery is not None:
            is_reachable = probe_discovery_api_reachable(baseline_discovery)
            if is_reachable:
                consecutive_down = 0
            else:
                consecutive_down += 1
        else:
            discovery_info = probe_discovery(
                base_dir,
                expected_edition=expected_edition,
            )
            if discovery_info is None:
                consecutive_down += 1
            else:
                consecutive_down = 0
        if consecutive_down >= 2:
            return True
        if deadline.expired():
            return False
        sleep_seconds(RESTART_POLL_INTERVAL_SECONDS)
