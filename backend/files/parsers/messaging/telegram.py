"""SoAI - Telegram export parsing [backend/files/parsers/messaging/telegram.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, override

from core.errors.exceptions import ValidationError
from core.files.types import ParsedDocument
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict
from core.timing.formatting import parse_iso_datetime_optional
from core.types.json import is_json_dict
from files.parsers.messaging.messaging_parser_base import MessagingParserBase

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("TelegramParser",)


class TelegramParser(MessagingParserBase):
    platform_name = "Telegram"

    def _extract_text(self, text_field: JSONValue) -> str:
        if isinstance(text_field, str):
            return text_field
        if isinstance(text_field, list):
            parts: list[str] = []
            for item in text_field:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "".join(parts)
        return str(text_field) if text_field is not None else ""

    def _parse_message(self, message: JSONDict) -> str | None:
        message_type = message.get("type", "message")
        if message_type == "service":
            action = str(message.get("action", "unknown action"))
            actor = str(message.get("actor", "Someone"))
            date_str = str(message.get("date", "") or "")
            timestamp = parse_iso_datetime_optional(date_str)
            return self._format_message(timestamp, "System", f"{actor} {action}")
        sender_value = message.get("from", message.get("actor", "Unknown"))
        sender = str(sender_value) if sender_value is not None else "Unknown"
        date_str = str(message.get("date", "") or "")
        timestamp = parse_iso_datetime_optional(date_str)
        text = self._extract_text(message.get("text", ""))
        if message.get("photo"):
            text = self._format_media_reference("Photo", str(message["photo"]))
        elif message.get("file"):
            media_type = message.get("media_type", "File")
            text = self._format_media_reference(str(media_type).title(), str(message["file"]))
        elif message.get("sticker_emoji"):
            text = f"[Sticker: {message['sticker_emoji']!s}]"
            if not text.strip():
                return None
        return self._format_message(timestamp, sender, text)

    def _append_messages(
        self,
        messages_list: list[str],
        participants: set[str],
        raw_messages: JSONValue,
    ) -> None:
        if not isinstance(raw_messages, list):
            return
        for message_entry in raw_messages:
            if not is_json_dict(message_entry):
                continue
            parsed = self._parse_message(message_entry)
            if parsed:
                messages_list.append(parsed)
                sender = message_entry.get("from", message_entry.get("actor"))
                if isinstance(sender, str) and sender:
                    participants.add(sender)

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        with open_text(file_path, encoding="utf-8") as file_handle:
            try:
                data = parse_json_dict(file_handle.read(), field="Telegram export")
            except ValidationError as exception:
                raise ValidationError("Invalid Telegram export format") from exception
        payload = data
        messages_list, participants = self._init_message_context()
        chat_name = "Telegram Chat"
        chats = payload.get("chats")
        if isinstance(chats, dict):
            chat_list = chats.get("list")
            if isinstance(chat_list, list):
                for chat_entry in chat_list:
                    if not is_json_dict(chat_entry):
                        continue
                    chat_name = str(chat_entry.get("name", "Unknown Chat"))
                    chat_messages = chat_entry.get("messages")
                    self._append_messages(messages_list, participants, chat_messages)
        elif "messages" in payload:
            chat_name = str(payload.get("name", "Telegram Chat"))
            raw_messages = payload.get("messages")
            if not isinstance(raw_messages, list):
                raise ValidationError("Invalid Telegram export format")
            self._append_messages(messages_list, participants, raw_messages)
        else:
            raise ValidationError("Invalid Telegram export format")
        return self._build_messaging_result(
            chat_name=chat_name,
            messages=messages_list,
            participants=participants,
        )
