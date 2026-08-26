"""SoAI - External service exception types [backend/core/errors/external_service_exception.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import SoAIError, build_error_init_kwargs

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("ExternalServiceError", "MCPError")


class ExternalServiceError(SoAIError):
    code: str | int = "external_service_error"
    http_status = 502
    is_transient = True


class MCPError(ExternalServiceError):
    code: str | int = "mcp_error"
    http_status = 502
    is_transient = True

    def __init__(
        self,
        message: str,
        *,
        rpc_code: int = -32603,
        rpc_data: JSONValue | None = None,
        details: Mapping[str, JSONValue] | None = None,
        operation: str | None = None,
        cause: BaseException | None = None,
        trace_id: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        error_kwargs = build_error_init_kwargs(details, operation, cause, trace_id, headers)
        super().__init__(
            message,
            **error_kwargs,
        )
        self.rpc_code = rpc_code
        self.rpc_data = rpc_data

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.message,),
            {
                "rpc_code": self.rpc_code,
                "rpc_data": self.rpc_data,
                "details": self.details,
                "operation": self.operation,
                "cause": self.cause,
                "trace_id": self.trace_id,
                "headers": self.headers,
            },
        )
