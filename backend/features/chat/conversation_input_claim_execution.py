"""SoAI - Claimed durable Chat input preparation [backend/features/chat/conversation_input_claim_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.validation.record_fields import (
    require_int,
    require_json_object,
    require_non_empty_str,
)
from features.api.routes.webui.conversation_input_queue_delivery_events import (
    publish_knowledge_events_from_delivery_result,
)
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_input_cancellation_admission import (
    terminalize_claimed_input_if_cancelled,
)
from features.chat.conversation_input_execution import (
    execute_claimed_conversation_input,
)
from features.messaging.input_media_ingestion import prepare_messaging_input_media

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("execute_claimed_conversation_input_preparation",)

OPERATION = "app.background.conversation_input_dispatcher.worker"


async def _publish_materialization(
    api_dependencies: ApiDependencies,
    materialized: JSONDict,
    *,
    logger: LoggerProtocol,
) -> None:
    user_id = require_int(
        materialized.get("user_id"),
        label="Materialized conversation input owner",
        build_error=StateError,
        minimum=1,
    )
    conv_id = require_non_empty_str(
        materialized.get("conv_id"),
        label="Materialized conversation input conversation",
        build_error=StateError,
    )
    if materialized.get("was_materialized") is True:
        message_count = require_int(
            materialized.get("message_count"),
            label="Materialized conversation input message count",
            build_error=StateError,
            minimum=0,
        )
        last_modified_at_ms = require_int(
            materialized.get("conversation_last_modified_at_ms"),
            label="Materialized conversation input revision",
            build_error=StateError,
            minimum=1,
        )
        conversation_title_value = materialized.get("conversation_title")
        conversation_title = (
            require_non_empty_str(
                conversation_title_value,
                label="Materialized conversation input title",
                build_error=StateError,
            )
            if conversation_title_value is not None
            else None
        )
        publication = publish_conversation_updated_and_message_saved(
            api_dependencies.event_bus,
            user_id=user_id,
            conv_id=conv_id,
            message_count=message_count,
            last_modified_at_ms=last_modified_at_ms,
            message=require_json_object(
                materialized.get("materialized_message"),
                label="Materialized conversation input message",
                build_error=StateError,
                invalid_message="Materialized conversation input message is invalid.",
            ),
            title=conversation_title,
        )
        try:
            await publication
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                coerce_to_soai_error(exception, operation=OPERATION),
                message="Conversation input materialization event publication failed.",
                operation=OPERATION,
                level="debug",
                details={"user_id": user_id, "conv_id": conv_id},
            )
        await publish_knowledge_events_from_delivery_result(api_dependencies, materialized)
    await publish_current_input_queue_changed(
        api_dependencies=api_dependencies,
        user_id=user_id,
        conv_id=conv_id,
    )


async def execute_claimed_conversation_input_preparation(
    api_dependencies: ApiDependencies,
    *,
    claimed: JSONDict,
    claim_owner: str,
    server_boot_id: str,
    logger: LoggerProtocol,
) -> None:
    input_id = require_non_empty_str(
        claimed.get("input_id"),
        label="Conversation input id",
        build_error=StateError,
    )
    claim_generation = require_int(
        claimed.get("claim_generation"),
        label="Conversation input claim generation",
        build_error=StateError,
        minimum=1,
    )
    if await terminalize_claimed_input_if_cancelled(
        api_dependencies,
        claimed=claimed,
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    ):
        return
    media_preparation = await prepare_messaging_input_media(
        api_dependencies,
        input_record=claimed,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    if media_preparation.status == "failed":
        terminal_code = media_preparation.terminal_code
        if terminal_code is None:
            raise StateError("Messaging media failure is missing a terminal code.")
        terminal = await api_dependencies.database_input_execution.terminalize_input(
            input_id=input_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
            terminal_state="failed",
            terminal_code=terminal_code,
            terminal_args={},
        )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=require_int(
                terminal.get("user_id"),
                label="Failed Messaging media input owner",
                build_error=StateError,
                minimum=1,
            ),
            conv_id=require_non_empty_str(
                terminal.get("conv_id"),
                label="Failed Messaging media input conversation",
                build_error=StateError,
            ),
        )
        return
    claimed = media_preparation.input_record
    if await terminalize_claimed_input_if_cancelled(
        api_dependencies,
        claimed=claimed,
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    ):
        return
    materialized = await api_dependencies.database_input_execution.materialize_claimed_input(
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    if materialized.get("cancellation_accepted") is True:
        await terminalize_claimed_input_if_cancelled(
            api_dependencies,
            claimed=materialized,
            input_id=input_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
        )
        return
    materialized["model_settings"] = (
        await api_dependencies.database_input_execution.get_input_execution_settings(
            input_id=input_id,
        )
    )
    await _publish_materialization(api_dependencies, materialized, logger=logger)
    if await terminalize_claimed_input_if_cancelled(
        api_dependencies,
        claimed=materialized,
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    ):
        return
    await execute_claimed_conversation_input(
        api_dependencies,
        input_record=materialized,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
