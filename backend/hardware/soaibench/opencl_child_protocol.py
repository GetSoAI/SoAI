"""SoAI - Strict OpenCL child response protocol validation [backend/hardware/soaibench/opencl_child_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ProcessError
from core.hardware.soaibench_limits import MAX_CHILD_MESSAGE_BYTES
from core.logging.protocols import LoggerProtocol
from core.types.json import JSONDict, JSONValue
from hardware.soaibench.errors import SoAIBenchUnsupported

__all__ = ("validate_child_response",)


def protocol_error(message: str) -> ProcessError:
    return ProcessError(
        message,
        operation="hardware.soaibench.opencl_child",
        details={"failure_type": "invalid_response"},
    )


def validate_child_response(response: JSONDict, logger: LoggerProtocol) -> JSONDict:
    if response.get("ok") is True:
        if set(response) not in ({"ok", "preflight"}, {"ok", "phase"}, {"ok", "runtime"}):
            raise protocol_error("SoAI Bench OpenCL child response fields are invalid.")
        return response
    if response.get("ok") is not False:
        raise protocol_error("SoAI Bench OpenCL child response status is invalid.")
    reason = response.get("reason")
    message = response.get("message")
    diagnostic = response.get("diagnostic")
    if set(response) not in (
        {"ok", "reason", "message"},
        {"ok", "reason", "message", "diagnostic"},
    ):
        raise protocol_error("SoAI Bench OpenCL child failure fields are invalid.")
    failure_fields = _validated_failure_fields(reason, message, diagnostic)
    if failure_fields is None:
        raise protocol_error("SoAI Bench OpenCL child failure is invalid.")
    reason_text, message_text, diagnostic_text = failure_fields
    if diagnostic_text is not None:
        logger.error(
            "SoAI Bench OpenCL child diagnostic for %s: %s",
            reason_text,
            diagnostic_text,
        )
    raise SoAIBenchUnsupported(reason_text, message_text)


def _bounded_text(value: str) -> bool:
    return 0 < len(value.encode("utf-8")) <= MAX_CHILD_MESSAGE_BYTES


def _validated_failure_fields(
    reason: JSONValue,
    message: JSONValue,
    diagnostic: JSONValue,
) -> tuple[str, str, str | None] | None:
    if not isinstance(reason, str) or not _bounded_text(reason):
        return None
    if not isinstance(message, str) or not _bounded_text(message):
        return None
    if diagnostic is not None and (
        not isinstance(diagnostic, str) or not _bounded_text(diagnostic)
    ):
        return None
    return reason, message, diagnostic
