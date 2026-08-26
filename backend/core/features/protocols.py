"""SoAI - Cross-subsystem feature contracts [backend/core/features/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, Protocol

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from core.database.mutation_requests import MutationAdmissionDraft
from core.events.types_base import Event

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONValue

__all__ = (
    "CommandDispatcherProtocol",
    "ResponseBuilderProtocol",
)


class ResponseBuilderProtocol(Protocol):
    def create_no_content_response(self) -> Response: ...

    def json_response_with_task_id(
        self,
        content: JSONValue,
        task_id: str,
        status_code: int = 200,
    ) -> JSONResponse: ...


class CommandDispatcherProtocol[TCommand: Event](Protocol):
    async def dispatch_and_respond(
        self,
        request: Request,
        command_class: type[TCommand],
        response_type: Literal["final", "accepted"],
        audit_action: str,
        audit_target: str,
        audit_details: Mapping[str, JSONValue] | None = None,
        command_fields: Mapping[str, JSONValue] | None = None,
        *,
        response_timeout: JSONValue | None = None,
        mutation_admission: MutationAdmissionDraft | None = None,
        sensitive_command_fields: frozenset[str] = frozenset(),
    ) -> Response: ...

    async def execute_model_mutation_command(
        self,
        request: Request,
        *,
        validator: Callable[[], Awaitable[None]] | None,
        command_class: type[TCommand],
        audit_action: str,
        audit_target: str,
        audit_details: dict[str, JSONValue],
        dispatch_fields: dict[str, JSONValue],
        success_status: int = 202,
    ) -> JSONResponse: ...
