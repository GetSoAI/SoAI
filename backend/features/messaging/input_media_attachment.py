"""SoAI - One Messaging provider attachment ingestion [backend/features/messaging/input_media_attachment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exceptions import StateError, ValidationError
from core.validation.record_fields import require_non_empty_str
from features.chat.direct_attachment_ingestion import (
    DirectAttachmentIngestionDependencies,
    ingest_direct_attachment,
)
from features.chat.direct_attachment_parsing import (
    DirectAttachmentParseDependencies,
    parse_direct_attachment,
)
from features.messaging.input_media_identity import require_messaging_media_input_identity
from features.messaging.provider_media_resolution import (
    ResolvedProviderMedia,
    resolve_discord_media,
    resolve_telegram_media,
    resolve_whatsapp_media,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("ingest_messaging_media_attachment",)


def _require_json_object(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict):
        raise StateError(f"{label} is invalid.")
    return value


async def _resolve_media(
    *,
    api_dependencies: ApiDependencies,
    platform: str,
    credentials: JSONDict,
    descriptor: JSONDict,
    source_metadata: JSONDict,
    max_bytes: int,
) -> ResolvedProviderMedia:
    if platform == "telegram":
        return await resolve_telegram_media(
            http_client=api_dependencies.http_client,
            runtime_flags=api_dependencies.runtime_flags,
            credentials=credentials,
            descriptor=descriptor,
            max_bytes=max_bytes,
        )
    if platform == "whatsapp":
        return await resolve_whatsapp_media(
            http_client=api_dependencies.http_client,
            runtime_flags=api_dependencies.runtime_flags,
            credentials=credentials,
            descriptor=descriptor,
            max_bytes=max_bytes,
        )
    if platform == "discord":
        return await resolve_discord_media(
            http_client=api_dependencies.http_client,
            runtime_flags=api_dependencies.runtime_flags,
            credentials=credentials,
            descriptor=descriptor,
            source_metadata=source_metadata,
            max_bytes=max_bytes,
        )
    raise ValidationError("Messaging input media platform is invalid.")


async def ingest_messaging_media_attachment(
    *,
    api_dependencies: ApiDependencies,
    input_record: JSONDict,
    account: JSONDict,
    descriptor: JSONDict,
    source_metadata: JSONDict,
) -> JSONDict:
    input_identity = require_messaging_media_input_identity(input_record)
    media_id = require_non_empty_str(
        descriptor.get("provider_media_id"),
        label="Messaging provider media id",
        build_error=StateError,
    )
    platform = require_non_empty_str(
        account.get("platform"),
        label="Messaging media platform",
        build_error=StateError,
    )
    credentials = _require_json_object(account.get("credentials"), "Messaging credentials")
    resolved = await _resolve_media(
        api_dependencies=api_dependencies,
        platform=platform,
        credentials=credentials,
        descriptor=descriptor,
        source_metadata=source_metadata,
        max_bytes=resolve_upload_limit_bytes(api_dependencies.config, UploadLimitType.FILE),
    )
    attachment_digest = hashlib.sha256(
        f"{input_identity.input_id}:{media_id}".encode("utf-8"),
    ).hexdigest()[:32]
    client_attachment_id = f"msg_{attachment_digest}"
    try:
        ingestion = await ingest_direct_attachment(
            deps=DirectAttachmentIngestionDependencies(
                config=api_dependencies.config,
                files=api_dependencies.files,
                database_attachments=api_dependencies.database_conversation_attachments,
                storage_manager=api_dependencies.storage_manager,
                token_collection=api_dependencies.token_collection,
                cancellation_history=api_dependencies.cancellation_history,
                cancellation_event_bus=api_dependencies.cancellation_event_bus,
            ),
            read_chunk=resolved.stream.read_chunk,
            declared_size=resolved.declared_size,
            declared_content_type=resolved.mime_type,
            display_name=resolved.filename,
            source_filename=resolved.filename,
            conv_id=input_identity.conv_id,
            user_id=input_identity.user_id,
            client_attachment_id=client_attachment_id,
            cancellation_id=(f"messaging-media-{input_identity.input_id}-{client_attachment_id}"),
        )
    finally:
        await resolved.close()
    attachment = ingestion.attachment
    if attachment.get("parse_state") == "pending":
        parse_result = await parse_direct_attachment(
            deps=DirectAttachmentParseDependencies(
                config=api_dependencies.config,
                files=api_dependencies.files,
                database_files=api_dependencies.database_files,
                database_attachments=api_dependencies.database_conversation_attachments,
                document_reader=api_dependencies.document_reader,
                parser_registry_factory=api_dependencies.parser_registry_factory,
                event_bus=api_dependencies.event_bus,
            ),
            attachment=attachment,
        )
        if parse_result.attachment is not None:
            attachment = parse_result.attachment
    if attachment.get("parse_state") != "ready":
        raise ValidationError("Messaging provider attachment parsing failed.")
    return attachment
