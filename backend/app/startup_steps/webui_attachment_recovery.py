"""SoAI - Startup recovery for WebUI conversation attachments [backend/app/startup_steps/webui_attachment_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from app.background.webui_attachment_cleanup_run import run_webui_attachment_cleanup
from app.types_application import ApplicationContext
from core.errors.exceptions import StateError
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from features.chat.direct_attachment_parsing import (
    DirectAttachmentParseDependencies,
    parse_direct_attachment,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("recover_webui_conversation_attachments",)

_RECOVERY_BATCH_LIMIT = 500
_RECOVERY_PARSE_CONCURRENCY = 4


def _require_recovery_string(attachment: JSONDict, field_name: str) -> str:
    value = attachment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"Attachment recovery {field_name} is invalid.")
    return value


def _require_recovery_int(attachment: JSONDict, field_name: str) -> int:
    value = attachment.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateError(f"Attachment recovery {field_name} is invalid.")
    return value


async def _recover_pending_attachment_parses(context: ApplicationContext) -> int:
    database_attachments = context.services.databases.conversation_attachments
    task_registry = context.api_runtime_singletons.attachment_parse_tasks
    recovered = 0
    cursor_created_at_ms: int | None = None
    cursor_attachment_id: str | None = None
    parse_dependencies = DirectAttachmentParseDependencies(
        config=context.services.configuration.config,
        files=context.services.configuration.files,
        database_users=context.services.databases.users,
        database_files=context.services.databases.files,
        database_attachments=database_attachments,
        document_reader=context.services.storage.document_reader,
        parser_registry_factory=context.services.storage.parser_registry_factory,
        event_bus=context.services.infrastructure.event_bus,
    )
    while True:
        pending = await database_attachments.list_pending_parse_attachments(
            limit=_RECOVERY_BATCH_LIMIT,
            cursor_created_at_ms=cursor_created_at_ms,
            cursor_attachment_id=cursor_attachment_id,
        )
        if not pending:
            return recovered
        recovered_in_batch: list[str] = []

        async def recover_one(
            attachment: JSONDict,
            attachment_id: str,
            recovered_attachment_ids: list[str],
        ) -> None:
            result = await parse_direct_attachment(
                deps=parse_dependencies,
                attachment=attachment,
            )
            if result.status == "parsed":
                recovered_attachment_ids.append(attachment_id)

        for offset in range(0, len(pending), _RECOVERY_PARSE_CONCURRENCY):
            tasks: list[asyncio.Task[None]] = []
            for attachment in pending[offset : offset + _RECOVERY_PARSE_CONCURRENCY]:
                cursor_created_at_ms = _require_recovery_int(attachment, "created_at_ms")
                cursor_attachment_id = _require_recovery_string(
                    attachment,
                    "attachment_id",
                )
                tasks.append(
                    await task_registry.schedule(
                        cursor_attachment_id,
                        partial(
                            recover_one,
                            attachment,
                            cursor_attachment_id,
                            recovered_in_batch,
                        ),
                    ),
                )
            await asyncio.gather(*tasks, return_exceptions=False)
        recovered += len(recovered_in_batch)


async def recover_webui_conversation_attachments(context: ApplicationContext) -> None:
    storage_root = resolve_managed_files_storage_root(
        context.services.configuration.config,
        context.services.configuration.files,
    )
    expired_count, expired_knowledge_count = await run_webui_attachment_cleanup(
        database_core=context.services.databases.core,
        database_attachments=context.services.databases.conversation_attachments,
        database_knowledge=context.services.databases.conversation_knowledge_attachments,
        event_bus=context.services.infrastructure.event_bus,
        logger=context.logging.logger,
        storage_root=storage_root,
        batch_limit=_RECOVERY_BATCH_LIMIT,
    )
    recovered_count = await _recover_pending_attachment_parses(context)
    if expired_count or expired_knowledge_count or recovered_count:
        context.logging.logger.info(
            "Recovered WebUI attachments on startup: expired=%s, knowledge_expired=%s, parsed=%s.",
            expired_count,
            expired_knowledge_count,
            recovered_count,
        )
