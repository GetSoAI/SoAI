"""SoAI - OpenAI command dispatch for pre-created tasks and staged uploads [backend/features/api/routes/openai/streaming_upload_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_requests import AudioTranscriptionRequestReceived
from core.files.upload_staging import cleanup_temp_file
from features.api.routes.openai.audio_transcription_responses import (
    negotiate_audio_transcription_response,
)
from features.api.runtime.command_publishing import construct_and_publish_command
from features.api.runtime.response_cleanup import (
    handle_dispatch_cancellation,
    handle_dispatch_soai_error,
    handle_dispatch_timeout,
    handle_dispatch_unexpected_error,
)
from features.api.runtime.response_collection import collect_final_response
from features.api.runtime.responses import apply_task_id_header

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = ("dispatch_openai_command_with_precreated_task",)


async def dispatch_openai_command_with_precreated_task(
    request: Request,
    *,
    api_context: ApiContext,
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    command_type: type[Event],
    command_fields: Mapping[str, JSONValue],
    response_timeout: float | None,
    staged_paths: list[str],
) -> Response:
    registry: TaskRegistryProtocol = api_context.dependencies.task_registry
    transcription_response_owns_cleanup = False
    try:
        cmd, reply_channel = await construct_and_publish_command(
            request,
            api_context.dependencies.event_bus,
            registry,
            command_type,
            task_id,
            reply_queue,
            dict(command_fields),
        )
        timeout_raw: float | None = (
            response_timeout if response_timeout is not None else cmd.TIMEOUT
        )
        timeout_value = 30.0
        if isinstance(timeout_raw, int | float) and not isinstance(timeout_raw, bool):
            candidate = float(timeout_raw)
            if math.isfinite(candidate):
                timeout_value = candidate
        if command_type is AudioTranscriptionRequestReceived:
            transcription_response_owns_cleanup = True
            return await negotiate_audio_transcription_response(
                request,
                api_context=api_context,
                task_id=task_id,
                reply_queue=reply_channel,
                command_fields=dict(command_fields),
                staged_paths=tuple(staged_paths),
            )
        response = await collect_final_response(
            request,
            registry,
            reply_channel,
            task_id,
            cmd,
            dict(command_fields),
            timeout_value,
        )
        apply_task_id_header(response, task_id)
        return response
    except asyncio.CancelledError:
        await handle_dispatch_cancellation(registry, task_id, request.state.context)
        raise
    except TimeoutError:
        await handle_dispatch_timeout(request, registry, task_id, command_type.__name__)
    except SoAIError as exception:
        await handle_dispatch_soai_error(registry, task_id, exception)
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        await handle_dispatch_unexpected_error(registry, task_id, exception)
        raise
    finally:
        if not transcription_response_owns_cleanup:
            for staged_path in staged_paths:
                await cleanup_temp_file(staged_path)
    raise ValidationError("Command dispatch completed without a response.")
