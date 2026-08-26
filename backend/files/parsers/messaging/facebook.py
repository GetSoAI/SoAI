"""SoAI - Facebook Messenger export parsing [backend/files/parsers/messaging/facebook.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, override

from core.files.types import ParsedDocument
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict
from core.types.json_value import coerce_json_dict
from files.parsers.messaging.messaging_parser_base import MessagingParserBase

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("FacebookMessengerParser",)


class FacebookMessengerParser(MessagingParserBase):
    platform_name = "Facebook Messenger"

    def _decode_facebook_encoding(self, text: str) -> str:
        if not text:
            return ""
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        with open_text(file_path, encoding="utf-8") as file_handle:
            data = parse_json_dict(file_handle.read(), field="Facebook Messenger export")
        messages_list, participants = self._init_message_context()
        title_value = data.get("title")
        title = (
            self._decode_facebook_encoding(title_value)
            if isinstance(title_value, str)
            else "Facebook Messenger Chat"
        )
        participants_value = data.get("participants")
        if isinstance(participants_value, list):
            for participant_value in participants_value:
                participant = coerce_json_dict(participant_value)
                if participant is None:
                    continue
                name_value = participant.get("name")
                if isinstance(name_value, str) and name_value:
                    participants.add(self._decode_facebook_encoding(name_value))
        messages_value = data.get("messages")
        raw_messages: list[JSONDict] = []
        if isinstance(messages_value, list):
            for message_value in messages_value:
                message = coerce_json_dict(message_value)
                if message is not None:
                    raw_messages.append(message)
        raw_messages.reverse()
        for message in raw_messages:
            sender_value = message.get("sender_name")
            sender = (
                self._decode_facebook_encoding(sender_value)
                if isinstance(sender_value, str)
                else "Unknown"
            )
            participants.add(sender)
            timestamp_ms_value = message.get("timestamp_ms")
            timestamp_ms: int | None
            if isinstance(timestamp_ms_value, bool):
                timestamp_ms = None
            elif isinstance(timestamp_ms_value, int | float):
                timestamp_ms = int(timestamp_ms_value)
            else:
                timestamp_ms = None
            timestamp = (
                datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC) if timestamp_ms else None
            )
            content_value = message.get("content")
            content = (
                self._decode_facebook_encoding(content_value)
                if isinstance(content_value, str)
                else ""
            )
            photos_value = message.get("photos")
            if isinstance(photos_value, list):
                for photo_value in photos_value:
                    photo = coerce_json_dict(photo_value)
                    if photo is None:
                        continue
                    uri_value = photo.get("uri")
                    uri = uri_value if isinstance(uri_value, str) and uri_value else "photo"
                    content += f" {self._format_media_reference('Photo', os.path.basename(uri))}"
            videos_value = message.get("videos")
            if isinstance(videos_value, list):
                for video_value in videos_value:
                    video = coerce_json_dict(video_value)
                    if video is None:
                        continue
                    uri_value = video.get("uri")
                    uri = uri_value if isinstance(uri_value, str) and uri_value else "video"
                    content += f" {self._format_media_reference('Video', os.path.basename(uri))}"
            audio_value = message.get("audio_files")
            if isinstance(audio_value, list):
                for audio_item_value in audio_value:
                    audio_item = coerce_json_dict(audio_item_value)
                    if audio_item is None:
                        continue
                    uri_value = audio_item.get("uri")
                    uri = uri_value if isinstance(uri_value, str) and uri_value else "audio"
                    content += f" {self._format_media_reference('Audio', os.path.basename(uri))}"
            gifs_value = message.get("gifs")
            if isinstance(gifs_value, list):
                for gif_value in gifs_value:
                    gif = coerce_json_dict(gif_value)
                    if gif is None:
                        continue
                    uri_value = gif.get("uri")
                    uri = uri_value if isinstance(uri_value, str) and uri_value else "gif"
                    content += f" {self._format_media_reference('GIF', os.path.basename(uri))}"
            sticker_value = message.get("sticker")
            sticker = coerce_json_dict(sticker_value)
            if sticker is not None:
                uri_value = sticker.get("uri")
                uri = uri_value if isinstance(uri_value, str) and uri_value else "sticker"
                content += f" {self._format_media_reference('Sticker', os.path.basename(uri))}"
            share_value = message.get("share")
            share = coerce_json_dict(share_value)
            if share is not None:
                link_value = share.get("link")
                link = link_value if isinstance(link_value, str) else ""
                if link:
                    content += f" [Shared Link: {link}]"
            call_duration_value = message.get("call_duration")
            if isinstance(call_duration_value, int | float) and not isinstance(
                call_duration_value,
                bool,
            ):
                duration = int(call_duration_value)
                content = f"[Call: {duration} seconds]"
            if content.strip():
                messages_list.append(self._format_message(timestamp, sender, content.strip()))
        return self._build_messaging_result(
            chat_name=title,
            messages=messages_list,
            participants=participants,
            extra_metadata={"title": title},
            include_chat_name=False,
        )
