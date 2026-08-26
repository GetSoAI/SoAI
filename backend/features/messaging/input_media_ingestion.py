"""SoAI - Messaging input media materialization [backend/features/messaging/input_media_ingestion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import content_part_from_file_attachment
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.record_fields import require_int, require_non_empty_str
from features.messaging.input_media_attachment import ingest_messaging_media_attachment
from features.messaging.input_media_identity import require_messaging_media_input_identity

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.types import ApiDependencies

    type MessagingMediaPreparationStatus = Literal["ready", "failed"]

__all__ = ("MessagingMediaPreparation", "prepare_messaging_input_media")

LOGGER_NAME = "SoAI.features.messaging.input_media_ingestion"
MAX_MEDIA_RETRIEVAL_ATTEMPTS = 3
OPERATION_INGEST = "messaging.input_media.ingest"


@dataclass(frozen=True, slots=True)
class MessagingMediaPreparation:
    status: MessagingMediaPreparationStatus
    input_record: JSONDict
    terminal_code: str | None = None


def _require_json_object(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict):
        raise StateError(f"{label} is invalid.")
    return value


async def prepare_messaging_input_media(
    api_dependencies: ApiDependencies,
    *,
    input_record: JSONDict,
    claim_owner: str,
    server_boot_id: str,
) -> MessagingMediaPreparation:
    descriptors_value = input_record.get("media_descriptors")
    if not isinstance(descriptors_value, list) or not descriptors_value:
        return MessagingMediaPreparation(status="ready", input_record=input_record)
    if input_record.get("transport_origin") != "messaging":
        raise StateError("Only Messaging inputs may contain provider media descriptors.")
    input_identity = require_messaging_media_input_identity(input_record)
    claim_generation = require_int(
        input_record.get("claim_generation"),
        label="Messaging media claim generation",
        build_error=StateError,
        minimum=1,
    )
    descriptors = [
        _require_json_object(descriptor, "Messaging media descriptor")
        for descriptor in descriptors_value
    ]
    media_ids = [descriptor.get("provider_media_id") for descriptor in descriptors]
    if len(media_ids) != len({str(media_id) for media_id in media_ids}):
        return MessagingMediaPreparation(
            status="failed",
            input_record=input_record,
            terminal_code="messaging_media_invalid",
        )
    source_metadata = _require_json_object(
        input_record.get("source_metadata"),
        "Messaging source metadata",
    )
    account_id = require_non_empty_str(
        source_metadata.get("account_id"),
        label="Messaging media account id",
        build_error=StateError,
    )
    platform = require_non_empty_str(
        source_metadata.get("platform"),
        label="Messaging media platform",
        build_error=StateError,
    )
    account = await api_dependencies.database_messaging_accounts.get_transport_account(
        account_id,
        platform,
    )
    if account is None or account.get("lifecycle_generation") != source_metadata.get(
        "account_generation"
    ):
        return MessagingMediaPreparation(
            status="failed",
            input_record=input_record,
            terminal_code="messaging_media_account_unavailable",
        )
    attachments: list[JSONValue] = []
    for descriptor in descriptors:
        for attempt in range(MAX_MEDIA_RETRIEVAL_ATTEMPTS):
            try:
                attachment = await ingest_messaging_media_attachment(
                    api_dependencies=api_dependencies,
                    input_record=input_record,
                    account=account,
                    descriptor=descriptor,
                    source_metadata=source_metadata,
                )
                attachments.append(content_part_from_file_attachment(attachment))
                break
            except (ValidationError, SecurityError) as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Messaging provider media was rejected.",
                    operation=OPERATION_INGEST,
                    details={"input_id": input_record.get("input_id")},
                    level="warning",
                )
                return MessagingMediaPreparation(
                    status="failed",
                    input_record=input_record,
                    terminal_code="messaging_media_invalid",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                if attempt + 1 >= MAX_MEDIA_RETRIEVAL_ATTEMPTS:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Messaging provider media retrieval failed after bounded retries.",
                        operation=OPERATION_INGEST,
                        details={"input_id": input_record.get("input_id")},
                        level="warning",
                    )
                    return MessagingMediaPreparation(
                        status="failed",
                        input_record=input_record,
                        terminal_code="messaging_media_unavailable",
                    )
                await api_dependencies.database_input_queue.require_active_claim(
                    input_id=input_identity.input_id,
                    claim_generation=claim_generation,
                    claim_owner=claim_owner,
                    server_boot_id=server_boot_id,
                )
                await asyncio.sleep(
                    compute_exponential_backoff_seconds(
                        attempt,
                        base_seconds=0.5,
                        maximum_seconds=2.0,
                    ),
                )
    updated = await api_dependencies.database_input_queue.attach_ingested_media(
        conv_id=input_identity.conv_id,
        user_id=input_identity.user_id,
        input_id=input_identity.input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        expected_media_descriptors=descriptors,
        attachment_content=attachments,
    )
    return MessagingMediaPreparation(status="ready", input_record=updated)
