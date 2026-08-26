"""SoAI - Messaging export parser base helpers [backend/files/parsers/messaging/messaging_parser_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from core.files.types import ParsedDocument
from files.parsers.blocking_parser import BlockingParser

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("MessagingParserBase",)


class MessagingParserBase(BlockingParser):
    platform_name: str = "Unknown"

    def _init_message_context(self) -> tuple[list[str], set[str]]:
        return [], set()

    def _derive_chat_name(self, file_path: str) -> str:
        return os.path.splitext(os.path.basename(file_path))[0]

    def _format_message(self, timestamp: datetime | None, sender: str, content: str) -> str:
        if timestamp:
            return f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] **{sender}**: {content}"
        return f"**{sender}**: {content}"

    def _format_media_reference(self, media_type: str, filename: str) -> str:
        return f"[{media_type}: {filename}]"

    def _build_header(
        self,
        chat_name: str,
        participants: list[str] | None = None,
        export_date: str | None = None,
    ) -> str:
        lines = [f"# Chat: {chat_name}", f"Platform: {self.platform_name}"]
        if participants:
            lines.append(f"Participants: {', '.join(participants)}")
        if export_date:
            lines.append(f"Export Date: {export_date}")
        lines.append("\n---\n")
        return "\n".join(lines)

    def _try_parse_datetime_formats(
        self,
        datetime_string: str,
        formats: list[str],
    ) -> datetime | None:
        if not datetime_string:
            return None
        for format_string in formats:
            try:
                return datetime.strptime(datetime_string.strip(), format_string)
            except ValueError:
                continue
        return None

    def _build_result(
        self,
        header: str,
        messages: list[str],
        chat_name: str,
        participants: set[str],
        extra_metadata: JSONDict | None = None,
        include_chat_name: bool = True,
    ) -> ParsedDocument:
        content = header + "\n".join(messages)
        metadata: JSONDict = {
            "platform": self.platform_name.lower().replace(" ", "_"),
            "message_count": len(messages),
            "participants": list(participants),
        }
        if include_chat_name:
            metadata["chat_name"] = chat_name
        if extra_metadata:
            metadata.update(extra_metadata)
        return ParsedDocument(content=content, metadata=metadata)

    def _build_messaging_result(
        self,
        chat_name: str,
        messages: list[str],
        participants: set[str],
        extra_metadata: JSONDict | None = None,
        export_date: str | None = None,
        include_chat_name: bool = True,
    ) -> ParsedDocument:
        header = self._build_header(
            chat_name=chat_name,
            participants=list(participants),
            export_date=export_date,
        )
        return self._build_result(
            header=header,
            messages=messages,
            chat_name=chat_name,
            participants=participants,
            extra_metadata=extra_metadata,
            include_chat_name=include_chat_name,
        )

    def _build_messaging_result_for_file(
        self,
        file_path: str,
        messages: list[str],
        participants: set[str],
    ) -> ParsedDocument:
        return self._build_messaging_result(
            chat_name=self._derive_chat_name(file_path),
            messages=messages,
            participants=participants,
        )
