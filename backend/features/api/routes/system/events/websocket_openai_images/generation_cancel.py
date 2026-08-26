"""SoAI - WebSocket OpenAI images generation cancellation handler [backend/features/api/routes/system/events/websocket_openai_images/generation_cancel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_openai_cancel_handling import (
    handle_openai_ws_cancel,
)
from features.api.routes.system.events.websocket_openai_images.payloads import (
    build_openai_images_generation_cancelled,
)
from features.api.routes.system.events.websocket_openai_runtime_cancellation import (
    cancel_openai_ws_active_task_runtime,
)
from features.api.routes.system.events.websocket_run_payloads import require_run_id

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiImageGenerationRuntime,
    )

__all__ = ("handle_openai_images_generation_cancel",)

LOGGER_NAME = "SoAI.features.api.generation_cancel"
OPERATION_IMAGES_GENERATION_CANCEL = "api_system.websocket.openai_images.generation.cancel"


async def handle_openai_images_generation_cancel(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    def cancel_runtime(runtime: OpenAiImageGenerationRuntime, reason: str) -> None:
        cancel_openai_ws_active_task_runtime(
            runtime=runtime,
            api_context=api_context,
            connection=connection,
            reason=reason,
            operation=OPERATION_IMAGES_GENERATION_CANCEL,
            logger=get_logger(LOGGER_NAME),
        )

    await handle_openai_ws_cancel(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        require_run_id=require_run_id,
        runtimes=connection.openai_image_generations,
        cancel_runtime=cancel_runtime,
        build_cancelled_event=lambda run_id, reason: build_openai_images_generation_cancelled(
            run_id=run_id,
            reason=reason,
        ),
        warn_label="OpenAI images generation cancelled",
    )
