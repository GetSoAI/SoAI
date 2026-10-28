"""SoAI - Budgeted probes and readiness errors for managed native runtimes [backend/core/system/native_runtime_probes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
import signal
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from core.concurrency.deadlines import MonotonicDeadline, deadline_after, earliest_deadline
from core.errors.exceptions import ProcessError, SoAIError, StateError
from core.system.commands import CommandResult, run_argv_capture
from core.system.native_image_budget import (
    WINDOWS_SECURITY_CHECK_SECONDS_PER_IMAGE,
    NativeImageAllowance,
    native_image_allowance,
)

__all__ = (
    "NativeProbeBudget",
    "RuntimeStartupTimeoutError",
    "RuntimeVerificationTimeoutError",
    "RuntimeVerificationFailedError",
    "capture_native_probe",
    "interpreter_image_allowance",
    "interpreter_probe_budget",
    "native_phase_seconds",
    "native_probe_budget",
    "run_native_probe",
    "runtime_timeout_error",
    "runtime_probe_failure_error",
)

FRESH_RUNTIME_GUIDANCE = (
    " Windows security checks of newly installed files can delay a runtime's first start."
)


class RuntimeVerificationTimeoutError(StateError):
    code: str | int = "runtime_verification_timeout"
    http_status = 504


class RuntimeVerificationFailedError(StateError):
    code: str | int = "runtime_verification_failed"


def runtime_probe_failure_error(
    *, exit_status: int, phase: str, diagnostic: str | None = None
) -> RuntimeVerificationFailedError:
    illegal_instruction = (os.name != "nt" and exit_status == -signal.SIGILL) or exit_status in (
        0xC000001D,
        -1073741795,
    )
    message = (
        "The runtime verification process stopped on an illegal instruction. Select a runtime compatible with this hardware or repair the backend installation."
        if illegal_instruction
        else "The runtime verification process failed. Repair the backend installation and review its diagnostics."
    )
    error = RuntimeVerificationFailedError(
        message,
        details={"phase": phase, "exit_status": exit_status, "stderr": diagnostic},
    )
    error.public_message = message
    error.public_details = {
        "reason": (
            "runtime_probe_illegal_instruction" if illegal_instruction else "runtime_probe_exit"
        ),
        "exit_status": exit_status,
    }
    return error


class RuntimeStartupTimeoutError(ProcessError):
    code: str | int = "runtime_startup_timeout"
    http_status = 504


@dataclass(frozen=True, slots=True)
class NativeProbeBudget:
    allowance: NativeImageAllowance
    deadline: MonotonicDeadline
    phase_ordinary_seconds: float

    def phase_seconds(self, ordinary_seconds: float | None = None) -> float:
        phase_ordinary = (
            self.phase_ordinary_seconds if ordinary_seconds is None else ordinary_seconds
        )
        image_seconds = WINDOWS_SECURITY_CHECK_SECONDS_PER_IMAGE * self.allowance.native_image_count
        return phase_ordinary + image_seconds


def runtime_timeout_error[ReadinessError: SoAIError](
    error_type: type[ReadinessError],
    *,
    subject: str,
    allowance: NativeImageAllowance,
) -> ReadinessError:
    message = f"{subject} did not finish within {math.ceil(allowance.seconds)} seconds." + (
        FRESH_RUNTIME_GUIDANCE if allowance.native_image_count else ""
    )
    error = error_type(
        message,
        details={
            "allowance_seconds": allowance.seconds,
            "ordinary_seconds": allowance.ordinary_seconds,
            "native_image_candidates": allowance.native_image_count,
            "inventory_complete": allowance.inventory_complete,
            "allowance_constrained": allowance.constrained,
        },
    )
    error.public_message = message
    return error


def native_probe_budget(
    ordinary_seconds: float,
    *,
    roots: Iterable[str],
    shallow_roots: Iterable[str] = (),
    excluded_names: Iterable[str] = (),
    probe_count: int = 1,
    ceiling: MonotonicDeadline | None = None,
) -> NativeProbeBudget:
    allowance = native_image_allowance(
        ordinary_seconds * probe_count,
        roots=roots,
        shallow_roots=shallow_roots,
        excluded_names=excluded_names,
        ceiling_seconds=None if ceiling is None else ceiling.remaining_seconds(),
    )
    deadline = deadline_after(allowance.seconds)
    return NativeProbeBudget(
        allowance=allowance,
        deadline=earliest_deadline(deadline, ceiling) or deadline,
        phase_ordinary_seconds=ordinary_seconds,
    )


def _interpreter_roots(
    python_executable: str, *, environment: bool
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    base_prefix = os.path.abspath(sys.base_prefix)
    roots = [python_executable, os.path.join(base_prefix, "DLLs")]
    environment_root = os.path.dirname(os.path.dirname(os.path.abspath(python_executable)))
    if environment and os.path.isfile(os.path.join(environment_root, "pyvenv.cfg")):
        roots.append(environment_root)
    return tuple(roots), (os.path.dirname(python_executable), base_prefix)


def interpreter_image_allowance(
    python_executable: str, *, ordinary_seconds: float, environment: bool = False
) -> NativeImageAllowance:
    roots, shallow_roots = _interpreter_roots(python_executable, environment=environment)
    return native_image_allowance(ordinary_seconds, roots=roots, shallow_roots=shallow_roots)


def interpreter_probe_budget(
    python_executable: str,
    *,
    ordinary_seconds: float,
    probe_count: int = 1,
    environment: bool = False,
    ceiling: MonotonicDeadline | None = None,
) -> NativeProbeBudget:
    roots, shallow_roots = _interpreter_roots(python_executable, environment=environment)
    return native_probe_budget(
        ordinary_seconds,
        roots=roots,
        shallow_roots=shallow_roots,
        probe_count=probe_count,
        ceiling=ceiling,
    )


def native_phase_seconds(budget: NativeProbeBudget, ordinary_seconds: float | None = None) -> float:
    return max(
        0.0, min(budget.phase_seconds(ordinary_seconds), budget.deadline.remaining_seconds())
    )


def run_native_probe(
    argv: Sequence[str],
    *,
    budget: NativeProbeBudget,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    encoding: str | None = None,
    errors: str | None = None,
) -> CommandResult:
    remaining = native_phase_seconds(budget)
    if remaining <= 0:
        return CommandResult(
            stdout="", return_code=124, stderr="The probe deadline was exhausted.", timed_out=True
        )
    return run_argv_capture(
        argv,
        timeout=max(1, math.ceil(remaining)),
        env=env,
        cwd=cwd,
        encoding=encoding,
        errors=errors,
    )


def capture_native_probe(
    argv: Sequence[str],
    *,
    budget: NativeProbeBudget,
    subject: str,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    encoding: str | None = None,
    errors: str | None = None,
) -> CommandResult:
    result = run_native_probe(
        argv, budget=budget, env=env, cwd=cwd, encoding=encoding, errors=errors
    )
    if result.timed_out:
        raise runtime_timeout_error(
            RuntimeVerificationTimeoutError, subject=subject, allowance=budget.allowance
        )
    return result
