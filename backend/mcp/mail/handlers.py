"""SoAI - Mail MCP tool handlers [backend/mcp/mail/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_request_id
from mcp.mail.resource_uris import MAIL_RESOURCE_URI
from mcp.shared.protocol_arguments import (
    optional_non_negative_int_argument,
    optional_positive_int_argument,
    optional_str_argument,
    require_str_argument,
)

if TYPE_CHECKING:
    from core.external_accounts.protocols import LinkedAccountQueryProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_mail_tool_handlers",)


def build_mail_tool_handlers(
    mail: MailServiceProtocol,
    *,
    account_queries: LinkedAccountQueryProtocol,
    require_authenticated_user_id: Callable[[str], int],
    request_context_provider: Callable[[], RequestContext | None],
    notify_resource_updated: Callable[[str], Awaitable[None]],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    async def mail_accounts_list(arguments: JSONDict) -> JSONValue:
        _ = arguments
        return await account_queries.list_accounts(
            require_authenticated_user_id("mail_accounts_list"),
        )

    async def mail_folders_list(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_folders_list")
        account_id = require_str_argument(arguments, "account_id")
        return await mail.list_folders(user_id=user_id, account_id=account_id, arguments=arguments)

    async def mail_messages_list(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_messages_list")
        folder_id = require_str_argument(arguments, "folder_id")
        return await mail.list_messages(user_id=user_id, folder_id=folder_id, arguments=arguments)

    async def mail_message_read(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_message_read")
        message_id = require_str_argument(arguments, "message_id")
        return await mail.read_message(
            user_id=user_id,
            message_id=message_id,
            part_id=optional_str_argument(arguments, "part_id"),
            max_chars=optional_positive_int_argument(arguments, "max_chars", 50_000),
            offset_chars=optional_non_negative_int_argument(arguments, "offset_chars", 0),
        )

    async def mail_attachment_download(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_attachment_download")
        attachment_id = require_str_argument(arguments, "attachment_id")
        request_context = request_context_provider() or _build_request_context(
            user_id=user_id,
            operation="mail_attachment_download",
        )
        return await mail.download_attachment(
            user_id=user_id,
            attachment_id=attachment_id,
            request_context=request_context,
        )

    async def mail_account_sync(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_account_sync")
        result = await mail.sync_account(
            user_id=user_id,
            account_id=require_str_argument(arguments, "account_id"),
            folder_id=optional_str_argument(arguments, "folder_id"),
        )
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    async def mail_messages_remote_search(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_messages_remote_search")
        result = await mail.remote_search_messages(
            user_id=user_id,
            account_id=require_str_argument(arguments, "account_id"),
            arguments=arguments,
        )
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    async def mail_folder_backfill(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_folder_backfill")
        result = await mail.backfill_folder(
            user_id=user_id,
            folder_id=require_str_argument(arguments, "folder_id"),
            arguments=arguments,
        )
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    async def mail_message_compose(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_message_compose")
        result = await mail.compose_message(user_id=user_id, payload=arguments)
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    async def mail_message_update(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_message_update")
        result = await mail.update_message(
            user_id=user_id,
            message_id=require_str_argument(arguments, "message_id"),
            action=require_str_argument(arguments, "action"),
            destination_folder_id=optional_str_argument(arguments, "destination_folder_id"),
        )
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    async def mail_folder_update(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("mail_folder_update")
        result = await mail.update_folder(
            user_id=user_id,
            account_id=require_str_argument(arguments, "account_id"),
            action=require_str_argument(arguments, "action"),
            folder_id=optional_str_argument(arguments, "folder_id"),
            folder_name=optional_str_argument(arguments, "folder_name"),
        )
        await notify_resource_updated(MAIL_RESOURCE_URI)
        return result

    return {
        "mail_accounts_list": mail_accounts_list,
        "mail_folders_list": mail_folders_list,
        "mail_messages_list": mail_messages_list,
        "mail_message_read": mail_message_read,
        "mail_attachment_download": mail_attachment_download,
        "mail_account_sync": mail_account_sync,
        "mail_messages_remote_search": mail_messages_remote_search,
        "mail_folder_backfill": mail_folder_backfill,
        "mail_message_compose": mail_message_compose,
        "mail_message_update": mail_message_update,
        "mail_folder_update": mail_folder_update,
    }


def _build_request_context(*, user_id: int, operation: str) -> RequestContext:
    trace_id = create_request_id(prefix=operation)
    return RequestContext(
        trace_id=trace_id,
        cancellation_id=trace_id,
        user_id=user_id,
        client_ip="internal",
    )
