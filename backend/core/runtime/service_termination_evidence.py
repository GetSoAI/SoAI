"""SoAI - Previous systemd service invocation termination evidence [backend/core/runtime/service_termination_evidence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

import psutil

from core.filesystem.text_read import read_text_if_exists
from core.platform.os import is_linux
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.serialization.json_parsing import parse_json_value_or_none
from core.system.commands import run_argv_capture

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict

    type ServiceTerminationType = Literal[
        "memory_exhausted",
        "stop_requested",
        "signal",
        "exited",
        "unknown",
        "permission_denied",
        "unavailable",
    ]

__all__ = (
    "ServiceTerminationEvidence",
    "classify_service_termination",
    "describe_service_termination",
    "resolve_previous_service_termination",
)

JOURNAL_QUERY_TIMEOUT_SECONDS = 5.0
JOURNAL_RECORD_LIMIT = 64
JOURNAL_OUTPUT_FIELDS = "INVOCATION_ID,MESSAGE_ID,JOB_TYPE,EXIT_CODE,EXIT_STATUS,UNIT_RESULT"
JOURNAL_PERMISSION_DENIED_MARKERS = (
    "insufficient permissions",
    "not seeing messages from other users and the system",
)
SYSTEMD_UNIT_OUT_OF_MEMORY_MESSAGE_ID = "fe6faa94e7774663a0da52717891d8ef"
SYSTEMD_UNIT_STOPPING_MESSAGE_ID = "de5b426a63be47a7b6ac3eaac82e2f6f"
SYSTEMD_OUT_OF_MEMORY_UNIT_RESULT = "oom-kill"
SYSTEMD_SIGNAL_EXIT_CODES = frozenset(("killed", "dumped"))
SYSTEMD_INVOCATION_ID_PATTERN = r"[0-9a-f]{32}"
SYSTEMD_USER_MANAGER_PATTERN = r"user@\d+\.service"
SYSTEMD_EXIT_STATUS_PATTERN = r"[A-Za-z0-9+_-]{1,32}"
PROCESS_CGROUP_PATH = "/proc/self/cgroup"


@dataclass(frozen=True, slots=True)
class ServiceTerminationEvidence:
    type: ServiceTerminationType
    detail: str | None = None
    ended_at_epoch_ms: int | None = None

    def attributes_memory_exhaustion(self, updated_at_epoch_ms: int) -> bool:
        return (
            self.type == "memory_exhausted"
            and self.ended_at_epoch_ms is not None
            and updated_at_epoch_ms <= self.ended_at_epoch_ms
        )


@cache
def resolve_previous_service_termination() -> ServiceTerminationEvidence:
    journal_query = _previous_invocation_journal_query()
    if journal_query is None:
        return ServiceTerminationEvidence(type="unavailable")
    argv, invocation_id = journal_query
    result = run_argv_capture(
        argv,
        timeout=JOURNAL_QUERY_TIMEOUT_SECONDS,
        encoding="utf-8",
        errors="replace",
    )
    if any(marker in result.stderr for marker in JOURNAL_PERMISSION_DENIED_MARKERS):
        return ServiceTerminationEvidence(type="permission_denied")
    if result.return_code != 0:
        return ServiceTerminationEvidence(type="unavailable")
    return classify_service_termination(
        _previous_invocation_records(_parse_journal_records(result.stdout), invocation_id),
    )


def classify_service_termination(records: Sequence[JSONDict]) -> ServiceTerminationEvidence:
    if not records:
        return ServiceTerminationEvidence(type="unknown")
    ended_at_epoch_ms = max(_record_epoch_ms(record) for record in records)
    if any(_is_out_of_memory_record(record) for record in records):
        return ServiceTerminationEvidence(
            type="memory_exhausted",
            ended_at_epoch_ms=ended_at_epoch_ms,
        )
    stop_requested = False
    for record in records:
        if _record_text(record, "MESSAGE_ID") == SYSTEMD_UNIT_STOPPING_MESSAGE_ID:
            stop_requested = True
            continue
        exit_code = _record_text(record, "EXIT_CODE")
        if exit_code is None:
            continue
        if stop_requested:
            break
        exit_status = _record_text(record, "EXIT_STATUS")
        detail = (
            exit_status
            if exit_status is not None and re.fullmatch(SYSTEMD_EXIT_STATUS_PATTERN, exit_status)
            else None
        )
        return ServiceTerminationEvidence(
            type="signal" if exit_code in SYSTEMD_SIGNAL_EXIT_CODES else "exited",
            detail=detail,
            ended_at_epoch_ms=ended_at_epoch_ms,
        )
    if stop_requested:
        return ServiceTerminationEvidence(
            type="stop_requested",
            ended_at_epoch_ms=ended_at_epoch_ms,
        )
    return ServiceTerminationEvidence(type="unknown", ended_at_epoch_ms=ended_at_epoch_ms)


def describe_service_termination(evidence: ServiceTerminationEvidence) -> str:
    if evidence.type == "memory_exhausted":
        return (
            "systemd recorded an out-of-memory kill for the previous SoAI service invocation. "
            "Free RAM or reduce loaded models, context length, batch size, or concurrency."
        )
    if evidence.type == "stop_requested":
        return "A stop was requested for the previous SoAI service invocation before it ended."
    if evidence.type == "signal":
        return (
            f"The previous SoAI service process was terminated by signal {evidence.detail or 'unknown'}; "
            "systemd recorded no out-of-memory kill for that invocation."
        )
    if evidence.type == "exited":
        return (
            f"The previous SoAI service process exited with status {evidence.detail or 'unknown'} "
            "without a recorded stop request."
        )
    if evidence.type == "unknown":
        return (
            "The current boot journal contains no termination record for the previous SoAI "
            "service invocation; the termination cause is unknown."
        )
    if evidence.type == "permission_denied":
        return (
            "The system journal could not be read because of insufficient permissions; "
            "the termination cause is unknown."
        )
    return "Native termination evidence is unavailable; the termination cause is unknown."


def _previous_invocation_journal_query() -> tuple[tuple[str, ...], str] | None:
    if not is_linux():
        return None
    unit = _current_systemd_service_unit()
    invocation_id = _current_invocation_id()
    journalctl_path = shutil.which("journalctl")
    if unit is None or invocation_id is None or journalctl_path is None:
        return None
    try:
        process_started_at_ms = read_process_create_time_ms(psutil.Process(os.getpid()))
    except psutil.Error:
        return None
    return (
        (
            journalctl_path,
            "--no-pager",
            "--boot=0",
            f"--until=@{process_started_at_ms / 1000.0:.3f}",
            "--output=json",
            f"--output-fields={JOURNAL_OUTPUT_FIELDS}",
            f"--lines={JOURNAL_RECORD_LIMIT}",
            "_PID=1",
            f"UNIT={unit}",
        ),
        invocation_id,
    )


def _current_systemd_service_unit() -> str | None:
    content = read_text_if_exists(PROCESS_CGROUP_PATH)
    if content is None:
        return None
    for line in content.splitlines():
        hierarchy, _, remainder = line.partition(":")
        controllers, _, cgroup_path = remainder.partition(":")
        if hierarchy != "0" and controllers != "name=systemd":
            continue
        components = [component for component in cgroup_path.split("/") if component]
        if any(re.fullmatch(SYSTEMD_USER_MANAGER_PATTERN, component) for component in components):
            return None
        services = [component for component in components if component.endswith(".service")]
        return services[-1] if services else None
    return None


def _current_invocation_id() -> str | None:
    invocation_id = os.environ.get("INVOCATION_ID", "")
    return invocation_id if re.fullmatch(SYSTEMD_INVOCATION_ID_PATTERN, invocation_id) else None


def _parse_journal_records(output: str) -> list[JSONDict]:
    records: list[JSONDict] = []
    for line in output.splitlines():
        parsed = parse_json_value_or_none(line, field="journal record")
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _previous_invocation_records(
    records: Sequence[JSONDict],
    current_invocation_id: str,
) -> list[JSONDict]:
    previous_invocation_id: str | None = None
    for record in reversed(records):
        invocation_id = _record_text(record, "INVOCATION_ID")
        if invocation_id is not None and invocation_id != current_invocation_id:
            previous_invocation_id = invocation_id
            break
    if previous_invocation_id is None:
        return []
    return [
        record
        for record in records
        if _record_text(record, "INVOCATION_ID") == previous_invocation_id
    ]


def _is_out_of_memory_record(record: JSONDict) -> bool:
    return (
        _record_text(record, "MESSAGE_ID") == SYSTEMD_UNIT_OUT_OF_MEMORY_MESSAGE_ID
        or _record_text(record, "UNIT_RESULT") == SYSTEMD_OUT_OF_MEMORY_UNIT_RESULT
    )


def _record_epoch_ms(record: JSONDict) -> int:
    timestamp = _record_text(record, "__REALTIME_TIMESTAMP")
    return int(timestamp) // 1000 if timestamp is not None and timestamp.isdigit() else 0


def _record_text(record: JSONDict, field: str) -> str | None:
    value = record.get(field)
    return value if isinstance(value, str) and value else None
