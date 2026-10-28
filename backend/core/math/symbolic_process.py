"""SoAI - Bounded symbolic math evaluation through a child process [backend/core/math/symbolic_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import sys
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ProcessError,
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.logging.trace import get_logger
from core.math.errors import MathExpressionError
from core.math.expression_limits import SYMBOLIC_MAX_CONCURRENT_EVALUATIONS
from core.math.result_projection import MATH_OUTCOMES, RESULT_TYPES
from core.math.symbolic_requests import build_symbolic_worker_request
from core.meta.paths import get_backend_root
from core.serialization.json_parsing import parse_json_dict
from core.system.async_process_capture import run_argv_capture_async
from core.system.resource_limits import PROCESS_MEMORY_SUPERVISION_EXIT_CODE
from core.timing.constants import CONTROL_TIMEOUT_SEC, INTERACTIVE_TIMEOUT_SEC
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.system.commands import CommandResult
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SYMBOLIC_MEMORY_EXIT_CODE",
    "SYMBOLIC_MEMORY_MESSAGE",
    "SYMBOLIC_WORKER_MODULE",
    "SymbolicMathRunner",
    "read_symbolic_worker_result",
)

LOGGER_NAME = "SoAI.core.math.symbolic_process"
SYMBOLIC_WORKER_MODULE = "core.math.symbolic_worker"
SYMBOLIC_MEMORY_EXIT_CODE = 3
SYMBOLIC_MEMORY_MESSAGE = "Symbolic evaluation exceeded the memory limit; simplify the expression or split it into smaller steps"
_OPERATION = "core.math.symbolic_process.evaluate"
_VALUE_KEYS = frozenset(
    {
        "result",
        "result_text",
        "result_type",
        "exact",
        "working_digits",
        "outcome",
        "note",
        "items",
        "cases",
        "entries",
        "components",
        "values",
        "constraints",
    }
)
_COMPONENT_KEYS = frozenset({"real", "imaginary"})
_LABEL_KEYS = frozenset({"name", "condition"})
_MAX_LOGGED_STDERR_CHARS = 2000


class SymbolicMathRunner:
    def __init__(self, *, timeout_sec: float = CONTROL_TIMEOUT_SEC) -> None:
        self._timeout_sec = timeout_sec
        self._admission = asyncio.Semaphore(SYMBOLIC_MAX_CONCURRENT_EVALUATIONS)

    async def evaluate(self, expression: str, variables: JSONValue | None) -> JSONDict:
        request = build_symbolic_worker_request(
            expression, variables, timeout_sec=self._timeout_sec
        )
        executable = sys.executable.strip()
        if not executable:
            raise _public_error(
                ServiceUnavailableError(
                    "Symbolic evaluation is unavailable because the Python interpreter could not be located."
                )
            )
        try:
            async with asyncio.timeout(INTERACTIVE_TIMEOUT_SEC):
                await self._admission.acquire()
        except TimeoutError as exception:
            raise _public_error(
                ServiceUnavailableError(
                    "Symbolic evaluation is busy with other calculations; retry shortly."
                )
            ) from exception
        try:
            result = await run_argv_capture_async(
                [executable, "-m", SYMBOLIC_WORKER_MODULE],
                timeout=self._timeout_sec,
                stdin_text=request,
                cwd=get_backend_root(),
            )
        finally:
            self._admission.release()
        return read_symbolic_worker_result(result, timeout_sec=self._timeout_sec)


def read_symbolic_worker_result(result: CommandResult, *, timeout_sec: float) -> JSONDict:
    if result.timed_out:
        raise _public_error(
            SoAITimeoutError(
                f"Symbolic evaluation exceeded the {timeout_sec:g}-second limit; simplify the expression or split it into smaller steps."
            )
        )
    if result.return_code == SYMBOLIC_MEMORY_EXIT_CODE:
        raise MathExpressionError(SYMBOLIC_MEMORY_MESSAGE)
    if result.return_code == PROCESS_MEMORY_SUPERVISION_EXIT_CODE:
        raise _worker_failure(
            result,
            reason="lost memory supervision",
            public_message="Symbolic evaluation stopped because its memory usage could not be monitored; check process permissions and retry.",
        )
    if result.return_code != 0:
        raise _worker_failure(result, reason="exited with an error")
    try:
        payload = parse_json_dict(
            result.stdout,
            field="symbolic evaluation response",
            reject_duplicate_keys=True,
        )
    except ValidationError as exception:
        raise _worker_failure(result, reason="returned malformed output") from exception
    status = payload.get("status")
    message = payload.get("message")
    if status == "error" and isinstance(message, str) and set(payload) == {"status", "message"}:
        raise MathExpressionError(message)
    projection = {key: value for key, value in payload.items() if key != "status"}
    if status == "ok" and _is_valid_projection(projection, extra_keys=("assignments",)):
        return projection
    raise _worker_failure(result, reason="returned an invalid response")


def _worker_failure(
    result: CommandResult,
    *,
    reason: str,
    public_message: str = "Symbolic evaluation failed unexpectedly; try again or use mode 'numeric'.",
) -> ProcessError:
    error = _public_error(
        ProcessError(
            public_message,
            operation=_OPERATION,
        )
    )
    logger = get_logger(LOGGER_NAME)
    log_exception(
        logger,
        error,
        message=f"Symbolic math worker {reason}.",
        operation=_OPERATION,
        details={"return_code": result.return_code},
    )
    logger.debug("Symbolic math worker stderr: %s", result.stderr[-_MAX_LOGGED_STDERR_CHARS:])
    return error


def _public_error[ErrorT: SoAIError](error: ErrorT) -> ErrorT:
    apply_public_error_payload(
        error,
        ErrorPublicPayload(code=error.code, message=error.message, http_status=error.http_status),
    )
    return error


def _is_valid_projection(
    projection: Mapping[str, JSONValue], *, extra_keys: Collection[str]
) -> bool:
    if not set(projection) <= _VALUE_KEYS | set(extra_keys):
        return False
    if not isinstance(projection.get("result_text"), str):
        return False
    if projection.get("result_type") not in RESULT_TYPES:
        return False
    if not isinstance(projection.get("exact"), bool):
        return False
    if "result" in projection and not _is_finite_number(projection["result"]):
        return False
    if "working_digits" in projection and not _is_positive_integer(projection["working_digits"]):
        return False
    if "outcome" in projection and projection["outcome"] not in MATH_OUTCOMES:
        return False
    if "note" in projection and not isinstance(projection["note"], str):
        return False
    if any(
        not isinstance(projection.get(key), str) for key in _LABEL_KEYS.intersection(extra_keys)
    ):
        return False
    return _has_valid_parts(projection) and _are_valid_projections(
        projection.get("assignments", []), extra_keys=("name",)
    )


def _has_valid_parts(projection: Mapping[str, JSONValue]) -> bool:
    components = projection.get("components", {})
    values = projection.get("values", {})
    entries = projection.get("entries", [])
    return (
        _are_valid_projections(projection.get("items", []), extra_keys=())
        and _are_valid_projections(projection.get("cases", []), extra_keys=("condition",))
        and isinstance(components, Mapping)
        and set(components) <= _COMPONENT_KEYS
        and _are_valid_projections(list(components.values()), extra_keys=())
        and isinstance(values, Mapping)
        and _are_valid_projections(list(values.values()), extra_keys=())
        and _is_text_list(projection.get("constraints", []))
        and isinstance(entries, list)
        and all(_is_text_list(row) for row in entries)
    )


def _are_valid_projections(projections: JSONValue, *, extra_keys: Collection[str]) -> bool:
    return isinstance(projections, list) and all(
        isinstance(projection, Mapping) and _is_valid_projection(projection, extra_keys=extra_keys)
        for projection in projections
    )


def _is_text_list(value: JSONValue) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_positive_integer(value: JSONValue) -> bool:
    return is_strict_int(value) and value > 0


def _is_finite_number(value: JSONValue) -> bool:
    if isinstance(value, bool):
        return False
    if is_strict_int(value):
        return True
    return isinstance(value, float) and math.isfinite(value)
