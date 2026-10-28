"""SoAI - Owned-session exit observation in an isolated interpreter [backend/core/process/group_exit_observation_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys

from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import ProcessError, ValidationError
from core.meta.paths import get_backend_root
from core.process.group_exit_observation import (
    OwnedGroupExitObservation,
    observe_owned_process_group,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.system.commands import run_argv_capture
from core.types.json import JSONDict

__all__ = (
    "main",
    "observe_owned_process_group_isolated",
)

PROBE_MODULE = "core.process.group_exit_observation_probe"
PROBE_DIAGNOSTIC_MAX_CHARS = 400


def observe_owned_process_group_isolated(
    group_id: int, *, deadline: MonotonicDeadline
) -> OwnedGroupExitObservation:
    if deadline.expired():
        return OwnedGroupExitObservation.UNVERIFIED
    executable = sys.executable.strip()
    if not executable:
        raise ProcessError("No Python interpreter is available to observe the owned process group.")
    result = run_argv_capture(
        [executable, "-m", PROBE_MODULE, str(group_id), str(deadline.deadline_monotonic)],
        timeout=deadline.remaining_seconds(),
        cwd=get_backend_root(),
    )
    if result.timed_out:
        return OwnedGroupExitObservation.UNVERIFIED
    report = _probe_report(result.stdout) if result.return_code == 0 else None
    if report is not None:
        process_error = report.get("process_error")
        if isinstance(process_error, str) and process_error:
            raise ProcessError(process_error)
        for observation in OwnedGroupExitObservation:
            if report.get("observation") == observation.value:
                return observation
    raise ProcessError(
        "Owned process-group observation probe failed.",
        details={
            "return_code": result.return_code,
            "stderr": result.stderr.strip()[-PROBE_DIAGNOSTIC_MAX_CHARS:],
        },
    )


def _probe_report(stdout: str) -> JSONDict | None:
    try:
        return parse_json_dict(stdout, field=PROBE_MODULE, reject_duplicate_keys=True)
    except ValidationError:
        return None


def main() -> None:
    group_id = int(sys.argv[1])
    deadline = MonotonicDeadline(float(sys.argv[2]))
    try:
        report: JSONDict = {
            "observation": observe_owned_process_group(group_id, deadline=deadline).value
        }
    except ProcessError as exception:
        report = {"process_error": exception.message}
    sys.stdout.write(serialize_json_compact_stable_strict(report))


if __name__ == "__main__":
    main()
