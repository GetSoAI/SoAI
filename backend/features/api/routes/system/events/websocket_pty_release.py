"""SoAI - Identity-targeted PTY release [backend/features/api/routes/system/events/websocket_pty_release.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError
from core.errors.public_projection import project_public_error
from core.mutations.identifiers import require_mutation_request_id
from core.state.access import AccessAction
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.terminal.acquisition_errors import PTYAcquisitionError
from core.types.json import JSONDict
from features.api.middleware.acl_enforcement import request_has_action
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import enqueue_pty_websocket_error
from features.api.routes.system.events.websocket_event_context import WebsocketEventRuntimeContext
from features.api.runtime.event_enqueue import enqueue_event_or_warn

__all__ = ("handle_pty_release",)


async def handle_pty_release(data: JSONDict, runtime_context: WebsocketEventRuntimeContext) -> None:
    runtime_id = data.get("runtime_id")
    acquisition_id = data.get("acquisition_id")
    identity: JSONDict = {"runtime_id": runtime_id, "acquisition_id": acquisition_id}
    try:
        if not isinstance(runtime_id, str) or not isinstance(acquisition_id, str):
            raise PTYAcquisitionError("PTY release requires runtime and acquisition identities.")
        require_mutation_request_id(runtime_id)
        require_mutation_request_id(acquisition_id)
        terminal = runtime_context.api_context.dependencies.terminal
        if terminal is None:
            raise PTYAcquisitionError("Terminal service unavailable; release is unconfirmed.")
        session_id = await terminal.release_pty_acquisition(
            runtime_id,
            acquisition_id,
            runtime_context.request_adapter.state.context.user_id,
            allow_new_acquisition=await request_has_action(
                runtime_context.connection.request, AccessAction.TERMINAL_USE
            ),
        )
    except (SoAIError, OSError) as exception:
        public_error = project_public_error(
            coerce_to_soai_error(exception), trace_id=runtime_context.trace_id
        )
        await enqueue_pty_websocket_error(
            runtime_context.enqueue_warning_tracker,
            runtime_context.connection.queue,
            runtime_context.trace_id,
            public_error.message,
            code="terminal_release_unconfirmed",
            details=identity,
        )
        return
    if session_id is not None and runtime_context.connection.pty_session_id == session_id:
        runtime_context.connection.pty_session_id = None
    enqueue_event_or_warn(
        runtime_context.enqueue_warning_tracker,
        runtime_context.connection.queue,
        build_websocket_event_payload(WebSocketEventTypes.PTY_RELEASED, identity),
        "PTY released",
    )
