"""SoAI - API command dispatcher orchestration [backend/features/api/runtime/command_dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, override

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from core.database.mutation_requests import MutationAdmissionDraft
from core.di.validation import require_dependencies
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.publication_errors import HardDeadlineExceededError
from core.events.types_base import Event
from core.features.protocols import CommandDispatcherProtocol
from core.logging.trace import get_logger
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.protocols import TaskRegistryProtocol
from features.api.runtime.audit import log_audit_event
from features.api.runtime.command_publishing import construct_and_publish_command
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.metadata_values import sanitize_dict_for_logging
from features.api.runtime.mutation_dispatch_notification import (
    notify_mutation_dispatch_requested,
)
from features.api.runtime.response_cleanup import (
    handle_dispatch_cancellation,
    handle_dispatch_soai_error,
    handle_dispatch_timeout,
    handle_dispatch_unexpected_error,
)
from features.api.runtime.response_collection import (
    collect_final_response,
)
from features.api.runtime.response_timeout import coerce_finite_response_timeout
from features.api.runtime.responses import (
    create_task_accepted_response,
    require_json_response,
)
from features.api.runtime.task_metadata import build_command_task_metadata
from features.api.runtime.task_preparation import (
    create_dispatch_task,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "CommandDispatcher",
    "CommandDispatcherDependencies",
)

LOGGER_NAME = "SoAI.features.api.command_dispatcher"


@dataclass(frozen=True, slots=True)
class CommandDispatcherDependencies:
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CommandDispatcherDependencies",
            event_bus=self.event_bus,
            task_registry=self.task_registry,
        )


class CommandDispatcher(CommandDispatcherProtocol[Event]):
    def __init__(self, deps: CommandDispatcherDependencies) -> None:
        self._event_bus = deps.event_bus
        self._task_registry = deps.task_registry

    def _require_response_type(self, response_type: str) -> Literal["final", "accepted"]:
        if response_type == "final":
            return "final"
        if response_type == "accepted":
            return "accepted"
        raise StateError(f"Unsupported command response type: {response_type}.")

    @override
    async def dispatch_and_respond(
        self,
        request: Request,
        command_class: type[Event],
        response_type: Literal["final", "accepted"],
        audit_action: str,
        audit_target: str,
        audit_details: Mapping[str, JSONValue] | None = None,
        command_fields: Mapping[str, JSONValue] | None = None,
        *,
        response_timeout: JSONValue | None = None,
        mutation_admission: MutationAdmissionDraft | None = None,
        sensitive_command_fields: frozenset[str] = frozenset(),
    ) -> Response:
        if not isinstance(command_class, type):
            raise StateError("command_class must be a class type.")
        resolved_response_timeout: float | None = None
        if response_timeout is not None:
            resolved_response_timeout = coerce_finite_response_timeout(response_timeout)
            if resolved_response_timeout is None:
                raise StateError("response_timeout must be a finite numeric value.")
        normalized_response_type = self._require_response_type(response_type)
        if mutation_admission is not None and normalized_response_type != "accepted":
            raise StateError("Durable mutation commands require accepted response mode.")
        resolved_command_fields = dict(command_fields) if command_fields is not None else {}
        unknown_sensitive_fields = sensitive_command_fields.difference(resolved_command_fields)
        if unknown_sensitive_fields:
            raise StateError("Sensitive command field declarations must reference command fields.")
        presentation_command_fields: dict[str, JSONValue] = {
            field_name: ("[REDACTED]" if field_name in sensitive_command_fields else field_value)
            for field_name, field_value in resolved_command_fields.items()
        }
        command_type: type[Event] = command_class
        log_audit_event(
            request,
            audit_action,
            audit_target,
            dict(audit_details) if audit_details is not None else None,
        )
        get_logger(LOGGER_NAME).debug(
            "Dispatching %s with fields %s",
            command_type.__name__,
            sanitize_dict_for_logging(presentation_command_fields),
        )
        task_metadata = build_command_task_metadata(
            request,
            command_type,
            audit_action,
            audit_target,
            dict(audit_details) if audit_details is not None else None,
            presentation_command_fields,
        )
        task, reply_queue = await create_dispatch_task(
            request,
            self._task_registry,
            command_type,
            task_metadata,
            request_source=resolve_request_source_for_request(request),
            delivery_mode="blocking" if normalized_response_type == "final" else "async",
            mutation_admission=mutation_admission,
        )
        if mutation_admission is not None:
            if task.mutation_admission_outcome == "accepted":
                await notify_mutation_dispatch_requested(self._event_bus)
            return create_task_accepted_response(
                task_id=task.task_id,
                commit_deadline_ts_ms=None,
            )
        cmd, reply_channel = await construct_and_publish_command(
            request,
            self._event_bus,
            self._task_registry,
            command_type,
            task.task_id,
            reply_queue,
            resolved_command_fields,
        )
        return await self._handle_response(
            request,
            normalized_response_type,
            task.task_id,
            reply_channel,
            cmd,
            resolved_command_fields,
            resolved_response_timeout,
        )

    async def _handle_response(
        self,
        request: Request,
        response_type: Literal["final", "accepted"],
        task_id: str,
        reply_channel: asyncio.Queue[Event],
        cmd: Event,
        command_fields: dict[str, JSONValue],
        response_timeout: float | None,
    ) -> Response:
        normalized_response_type = self._require_response_type(response_type)
        context = request.state.context
        if normalized_response_type == "accepted":
            return create_task_accepted_response(
                task_id=task_id,
                commit_deadline_ts_ms=None,
            )
        timeout_value = (
            response_timeout
            if response_timeout is not None
            else _resolve_default_timeout_seconds(cmd)
        )
        try:
            return await collect_final_response(
                request,
                self._task_registry,
                reply_channel,
                task_id,
                cmd,
                command_fields,
                timeout_value,
            )
        except asyncio.CancelledError:
            await handle_dispatch_cancellation(
                self._task_registry,
                task_id,
                context,
            )
            raise
        except (HardDeadlineExceededError, TimeoutError):
            await handle_dispatch_timeout(
                request,
                self._task_registry,
                task_id,
                type(cmd).__name__,
            )
        except SoAIError as exception:
            await handle_dispatch_soai_error(
                self._task_registry,
                task_id,
                exception,
            )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            await handle_dispatch_unexpected_error(
                self._task_registry,
                task_id,
                exception,
            )
            raise
        raise StateError("Command dispatch completed without a response.")

    @override
    async def execute_model_mutation_command(
        self,
        request: Request,
        *,
        validator: Callable[[], Awaitable[None]] | None,
        command_class: type[Event],
        audit_action: str,
        audit_target: str,
        audit_details: dict[str, JSONValue],
        dispatch_fields: dict[str, JSONValue],
        success_status: int = 202,
    ) -> JSONResponse:
        if validator:
            try:
                await validator()
            except ValueError as exception:
                raise_invalid_request(request, str(exception))
        command_fields = dict(dispatch_fields)
        response_timeout = command_fields.pop("response_timeout", None)
        response = await self.dispatch_and_respond(
            request,
            command_class,
            "final",
            audit_action,
            audit_target,
            audit_details,
            command_fields,
            response_timeout=response_timeout,
        )
        json_response = require_json_response(
            response,
            operation="api_runtime.execute_model_mutation_command",
            message="Model mutation command did not return a JSON response.",
        )
        json_response.status_code = success_status
        return json_response


def _resolve_default_timeout_seconds(cmd: Event) -> float:
    try:
        value = cmd.TIMEOUT
    except AttributeError:
        return 30.0
    if value is None:
        return 30.0
    candidate_timeout = coerce_finite_response_timeout(value)
    if candidate_timeout is None:
        raise StateError(f"{type(cmd).__name__}.TIMEOUT must be a finite numeric value.")
    return candidate_timeout
