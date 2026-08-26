"""SoAI - Discord export parsing [backend/files/parsers/messaging/discord.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, override

from core.files.types import ParsedDocument
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict
from core.timing.formatting import parse_iso_datetime_optional
from core.types.json_value import coerce_json_dict
from files.parsers.messaging.messaging_parser_base import MessagingParserBase

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DiscordParser",)


class DiscordParser(MessagingParserBase):
    platform_name = "Discord"

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        with open_text(file_path, encoding="utf-8") as file_handle:
            data = parse_json_dict(file_handle.read(), field="Discord export")
        guild = coerce_json_dict(data.get("guild"))
        if guild is not None:
            guild_name_value = guild.get("name")
            guild_name = (
                guild_name_value
                if isinstance(guild_name_value, str) and guild_name_value
                else "Unknown Server"
            )
        else:
            guild_name = "Direct Message"
        channel = coerce_json_dict(data.get("channel"))
        if channel is not None:
            channel_name_value = channel.get("name")
            channel_name = (
                channel_name_value
                if isinstance(channel_name_value, str) and channel_name_value
                else "unknown-channel"
            )
        else:
            channel_name = "chat"
        messages_list, participants = self._init_message_context()
        messages_value = data.get("messages")
        messages: list[JSONDict] = []
        if isinstance(messages_value, list):
            for message_value in messages_value:
                message = coerce_json_dict(message_value)
                if message is not None:
                    messages.append(message)
        for message in messages:
            author = coerce_json_dict(message.get("author")) or {}
            sender_value = author.get("name") or author.get("nickname")
            sender = sender_value if isinstance(sender_value, str) and sender_value else "Unknown"
            participants.add(sender)
            timestamp_value = message.get("timestamp")
            timestamp_str = timestamp_value if isinstance(timestamp_value, str) else ""
            timestamp = parse_iso_datetime_optional(timestamp_str)
            content_value = message.get("content")
            content = content_value if isinstance(content_value, str) else ""
            attachments_value = message.get("attachments")
            if isinstance(attachments_value, list):
                for attachment_value in attachments_value:
                    attachment = coerce_json_dict(attachment_value)
                    if attachment is None:
                        continue
                    file_name_value = attachment.get("fileName")
                    url_value = attachment.get("url")
                    attachment_name = (
                        file_name_value
                        if isinstance(file_name_value, str) and file_name_value
                        else url_value if isinstance(url_value, str) and url_value else "attachment"
                    )
                    content += f" {self._format_media_reference('Attachment', attachment_name)}"
            embeds_value = message.get("embeds")
            if isinstance(embeds_value, list) and (not content.strip()):
                embed_titles: list[str] = []
                for embed_value in embeds_value:
                    embed = coerce_json_dict(embed_value)
                    if embed is None:
                        continue
                    title_value = embed.get("title")
                    embed_titles.append(
                        title_value if isinstance(title_value, str) and title_value else "Embed",
                    )
                if embed_titles:
                    content = f"[Embed: {', '.join(embed_titles)}]"
            if content.strip():
                messages_list.append(self._format_message(timestamp, sender, content.strip()))
        chat_name = f"{guild_name} / #{channel_name}"
        return self._build_messaging_result(
            chat_name=chat_name,
            messages=messages_list,
            participants=participants,
            extra_metadata={"guild": guild_name, "channel": channel_name},
        )
