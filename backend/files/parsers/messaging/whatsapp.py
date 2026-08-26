"""SoAI - WhatsApp text and ZIP chat export parsing [backend/files/parsers/messaging/whatsapp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from re import Pattern
from typing import ClassVar, override

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.types import ParsedDocument
from core.validation.integers import require_non_negative_exact_int
from files.parsers.messaging.messaging_parser_base import MessagingParserBase
from files.parsers.text import read_text_file_with_encoding_detection

__all__ = ("WhatsAppParser",)


class WhatsAppParser(MessagingParserBase):
    platform_name = "WhatsApp"
    MAX_ZIP_MEMBERS = 10000
    MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 512 * MIB_BYTES
    MAX_CHAT_UNCOMPRESSED_BYTES = 16 * MIB_BYTES
    MAX_MEDIA_FILES_LISTED = 5000
    ZIP_READ_CHUNK_BYTES = 256 * 1024
    TIMESTAMP_PATTERNS: ClassVar[list[Pattern[str]]] = [
        re.compile(
            "^\\[?(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4}),?\\s*(\\d{1,2}:\\d{2}(?::\\d{2})?(?:\\s*[APap][Mm])?)\\]?\\s*-\\s*([^:]+):\\s*(.*)$",
        ),
        re.compile(
            "^(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4}),?\\s*(\\d{1,2}:\\d{2}(?::\\d{2})?(?:\\s*[APap][Mm])?)\\s*-\\s*([^:]+):\\s*(.*)$",
        ),
        re.compile(
            "^\\[(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4}),?\\s*(\\d{1,2}:\\d{2}:\\d{2})\\]\\s*([^:]+):\\s*(.*)$",
        ),
    ]
    SYSTEM_MESSAGE_PATTERN = re.compile(
        "^\\[?(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4}),?\\s*(\\d{1,2}:\\d{2}(?::\\d{2})?(?:\\s*[APap][Mm])?)\\]?\\s*-\\s*(.+)$",
    )
    MEDIA_PATTERNS: ClassVar[list[tuple[Pattern[str], str]]] = [
        (re.compile("<Media omitted>", re.IGNORECASE), "Media"),
        (re.compile("image omitted", re.IGNORECASE), "Image"),
        (re.compile("video omitted", re.IGNORECASE), "Video"),
        (re.compile("audio omitted", re.IGNORECASE), "Audio"),
        (re.compile("sticker omitted", re.IGNORECASE), "Sticker"),
        (re.compile("GIF omitted", re.IGNORECASE), "GIF"),
        (re.compile("document omitted", re.IGNORECASE), "Document"),
        (re.compile("Contact card omitted", re.IGNORECASE), "Contact"),
        (re.compile("<attached: ([^>]+)>", re.IGNORECASE), "Attachment"),
        (re.compile("(IMG-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Image"),
        (re.compile("(VID-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Video"),
        (re.compile("(PTT-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Voice Note"),
        (re.compile("(AUD-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Audio"),
        (re.compile("(STK-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Sticker"),
        (re.compile("(DOC-\\d+-WA\\d+\\.\\w+)", re.IGNORECASE), "Document"),
    ]
    DATE_FORMATS: ClassVar[list[str]] = [
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%m.%d.%Y",
        "%Y.%m.%d",
        "%d/%m/%y",
        "%m/%d/%y",
        "%y/%m/%d",
    ]
    TIME_FORMATS: ClassVar[list[str]] = [
        "%H:%M:%S",
        "%H:%M",
        "%I:%M:%S %p",
        "%I:%M %p",
        "%I:%M:%S%p",
        "%I:%M%p",
    ]

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime | None:
        time_str = time_str.strip().upper().replace(" ", "")
        for date_fmt in self.DATE_FORMATS:
            for time_fmt in self.TIME_FORMATS:
                try:
                    return datetime.strptime(f"{date_str} {time_str}", f"{date_fmt} {time_fmt}")
                except ValueError:
                    continue
        return None

    def _normalize_chat_name(self, chat_name: str) -> str:
        chat_name = re.sub("^WhatsApp Chat with ", "", chat_name, flags=re.IGNORECASE)
        return re.sub("_chat$", "", chat_name, flags=re.IGNORECASE)

    def _process_content(self, content: str) -> str:
        for pattern, media_type in self.MEDIA_PATTERNS:
            match = pattern.search(content)
            if match:
                if match.lastindex and match.lastindex >= 1:
                    return self._format_media_reference(media_type, match.group(1))
                return self._format_media_reference(media_type, "omitted")
        return content

    def _parse_whatsapp_text(self, text: str) -> tuple[list[str], list[str]]:
        lines = text.split("\n")
        messages: list[str] = []
        participants: set[str] = set()
        current_message: str | None = None
        current_sender: str | None = None
        current_timestamp: datetime | None = None
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            matched = False
            for pattern in self.TIMESTAMP_PATTERNS:
                match = pattern.match(line)
                if match:
                    if current_message is not None and current_sender:
                        processed = self._process_content(current_message)
                        messages.append(
                            self._format_message(current_timestamp, current_sender, processed),
                        )
                    date_str, time_str, sender, content = match.groups()
                    current_timestamp = self._parse_datetime(date_str, time_str)
                    sender_str = sender.strip()
                    current_sender = sender_str
                    current_message = content
                    participants.add(sender_str)
                    matched = True
                    break
            if not matched:
                sys_match = self.SYSTEM_MESSAGE_PATTERN.match(line)
                if sys_match:
                    if current_message is not None and current_sender:
                        processed = self._process_content(current_message)
                        messages.append(
                            self._format_message(current_timestamp, current_sender, processed),
                        )
                        current_message = None
                        current_sender = None
                    date_str, time_str, sys_content = sys_match.groups()
                    timestamp = self._parse_datetime(date_str, time_str)
                    messages.append(self._format_message(timestamp, "System", sys_content))
                elif current_message is not None:
                    current_message = f"{current_message}\n{line}"
        if current_message is not None and current_sender:
            processed = self._process_content(current_message)
            messages.append(self._format_message(current_timestamp, current_sender, processed))
        return (messages, list(participants))

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".zip":
            return self._parse_zip(file_path)
        return self._parse_txt(file_path)

    def _parse_txt(self, file_path: str) -> ParsedDocument:
        text, _ = read_text_file_with_encoding_detection(file_path)
        messages, participants = self._parse_whatsapp_text(text)
        chat_name = self._normalize_chat_name(self._derive_chat_name(file_path))
        return self._build_messaging_result(
            chat_name=chat_name,
            messages=messages,
            participants=set(participants),
        )

    def _parse_zip_text_member(self, data: bytes) -> str:
        if len(data) > self.MAX_CHAT_UNCOMPRESSED_BYTES:
            raise ValidationError(
                f"WhatsApp chat text file is too large after decompression ({len(data)} bytes).",
            )
        return data.decode("utf-8", errors="replace")

    def _parse_zip(self, file_path: str) -> ParsedDocument:
        with zipfile.ZipFile(file_path, "r") as zf:
            chat_file_info: zipfile.ZipInfo | None = None
            first_text_file_info: zipfile.ZipInfo | None = None
            media_files: list[str] = []
            media_files_truncated = False
            member_count = 0
            total_uncompressed_bytes = 0
            for member_info in zf.infolist():
                member_count += 1
                if member_count > self.MAX_ZIP_MEMBERS:
                    raise ValidationError(
                        f"WhatsApp ZIP export has too many entries ({member_count} > {self.MAX_ZIP_MEMBERS}).",
                    )
                member_size = require_non_negative_exact_int(
                    member_info.file_size,
                    type_message="WhatsApp ZIP export member size must be an integer.",
                    range_message="WhatsApp ZIP export member size must be >= 0.",
                )
                total_uncompressed_bytes += member_size
                if total_uncompressed_bytes > self.MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                    raise ValidationError(
                        f"WhatsApp ZIP export total uncompressed size is too large ({total_uncompressed_bytes} bytes > {self.MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES} bytes).",
                    )
                if member_info.is_dir():
                    continue
                lower_name = member_info.filename.lower()
                if lower_name.endswith(".txt"):
                    if first_text_file_info is None:
                        first_text_file_info = member_info
                    if "_chat" in lower_name or "whatsapp" in lower_name:
                        chat_file_info = member_info
                        continue
                if len(media_files) >= self.MAX_MEDIA_FILES_LISTED:
                    media_files_truncated = True
                    continue
                media_files.append(member_info.filename)
            if chat_file_info is None:
                chat_file_info = first_text_file_info
            if chat_file_info is None:
                raise ValidationError("No chat text file found in WhatsApp ZIP export")
            chat_file_size = require_non_negative_exact_int(
                chat_file_info.file_size,
                type_message="WhatsApp chat text file size must be an integer.",
                range_message="WhatsApp chat text file size must be >= 0.",
            )
            if chat_file_size > self.MAX_CHAT_UNCOMPRESSED_BYTES:
                raise ValidationError(
                    f"WhatsApp chat text file is too large after decompression ({chat_file_size} bytes > {self.MAX_CHAT_UNCOMPRESSED_BYTES} bytes).",
                )
            with zf.open(chat_file_info) as file_handle:
                chunks: list[bytes] = []
                while True:
                    chunk = file_handle.read(self.ZIP_READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    chunks.append(chunk)
                data = b"".join(chunks)
            text = self._parse_zip_text_member(data)
            messages, participants = self._parse_whatsapp_text(text)
            chat_name = self._normalize_chat_name(self._derive_chat_name(chat_file_info.filename))
            filtered_media_files = [
                media_file for media_file in media_files if not media_file.lower().endswith(".txt")
            ]
            if filtered_media_files:
                media_lines = [
                    f"- {media_file_entry}" for media_file_entry in sorted(filtered_media_files)
                ]
                if media_files_truncated:
                    media_lines.append(
                        f"- ... ({len(filtered_media_files)} listed; additional media files were omitted)",
                    )
                media_section = "\n".join(["\n\n---\n\n## Media Files\n", *media_lines, ""])
                messages.append(media_section)
            return self._build_messaging_result(
                chat_name=chat_name,
                messages=messages,
                participants=set(participants),
                extra_metadata={
                    "media_files": filtered_media_files,
                    "media_files_truncated": media_files_truncated,
                },
            )
