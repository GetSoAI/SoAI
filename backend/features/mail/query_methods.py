"""SoAI - Mail service query methods [backend/features/mail/query_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.external_accounts.listing_support import (
    paginate_json_items,
    resolve_direction,
    resolve_limit,
    resolve_order,
)
from features.mail.formatting import (
    format_mail_folder,
    format_mail_message,
)
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_account_context import require_mail_account_protocol
from features.mail.mail_record_context import load_folder_context
from features.mail.message_listing import (
    build_cache_coverage,
    filter_messages,
    folder_sort_key,
    message_sort_key,
)

__all__ = (
    "list_folders_method",
    "list_messages_method",
)


async def list_folders_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    arguments: JSONDict,
) -> JSONDict:
    account = await self.database_mail.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        raise ValidationError("Mail account not found.")
    limit = resolve_limit(
        self.config,
        arguments.get("limit"),
        "INTEGRATIONS.MAIL.LIMITS.LIST_DEFAULT",
        "INTEGRATIONS.MAIL.LIMITS.LIST_MAX",
    )
    order_by = resolve_order(
        arguments.get("order_by"),
        ("name", "unread_count", "message_count"),
        "name",
    )
    order_direction = resolve_direction(arguments.get("order_direction"), default_value="desc")
    folders = await self.database_mail.list_folders(user_id=user_id, account_id=account_id)
    protocol = require_mail_account_protocol(account)
    formatted = [format_mail_folder(folder, protocol=protocol) for folder in folders]
    formatted.sort(
        key=lambda item: folder_sort_key(item, order_by),
        reverse=(order_direction == "desc"),
    )
    page = paginate_json_items(
        items=formatted,
        cursor=coerce_optional_trimmed_str(arguments.get("cursor")),
        limit=limit,
        order_by=order_by,
        order_direction=order_direction,
        supported_sort_fields=("name", "unread_count", "message_count"),
    )
    return page


async def list_messages_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    folder_id: str,
    arguments: JSONDict,
) -> JSONDict:
    folder_context = await load_folder_context(
        self.database_mail,
        user_id=user_id,
        folder_id=folder_id,
    )
    limit = resolve_limit(
        self.config,
        arguments.get("limit"),
        "INTEGRATIONS.MAIL.LIMITS.LIST_DEFAULT",
        "INTEGRATIONS.MAIL.LIMITS.LIST_MAX",
    )
    order_by = resolve_order(
        arguments.get("order_by"),
        ("received_at_ms", "sent_at_ms", "subject", "from", "size_bytes"),
        "received_at_ms",
    )
    order_direction = resolve_direction(arguments.get("order_direction"), default_value="desc")
    messages = await self.database_mail.list_messages(user_id=user_id, folder_id=folder_id)
    filtered = filter_messages(messages, arguments)
    formatted = [
        format_mail_message(message, protocol=folder_context.protocol) for message in filtered
    ]
    formatted.sort(
        key=lambda item: message_sort_key(item, order_by),
        reverse=(order_direction == "desc"),
    )
    page = paginate_json_items(
        items=formatted,
        cursor=coerce_optional_trimmed_str(arguments.get("cursor")),
        limit=limit,
        order_by=order_by,
        order_direction=order_direction,
        supported_sort_fields=(
            "received_at_ms",
            "sent_at_ms",
            "subject",
            "from",
            "size_bytes",
        ),
    )
    page["cache_coverage"] = build_cache_coverage(messages, self.config)
    return page
