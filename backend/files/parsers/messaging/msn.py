"""SoAI - MSN Messenger export parsing [backend/files/parsers/messaging/msn.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import datetime
from typing import override

from defusedxml import ElementTree

from core.errors.exceptions import ValidationError
from core.files.types import ParsedDocument
from files.parsers.messaging.messaging_parser_base import MessagingParserBase

__all__ = ("MSNMessengerParser",)


class MSNMessengerParser(MessagingParserBase):
    platform_name = "MSN Messenger"

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        tree = ElementTree.parse(file_path)
        root = tree.getroot()
        if root is None:
            raise ValidationError(f"Invalid XML structure in file: {file_path}")
        messages_list, participants = self._init_message_context()
        log_element = root if root.tag == "Log" else root.find(".//Log")
        if log_element is None:
            log_element = root
        for message in log_element.iter("Message"):
            date_str = message.get("Date", message.get("DateTime", ""))
            time_str = message.get("Time", "")
            timestamp = self._parse_msn_datetime(date_str, time_str)
            from_elem = message.find("From")
            sender = "Unknown"
            if from_elem is not None:
                user_elem = from_elem.find("User")
                if user_elem is not None:
                    sender = user_elem.get("FriendlyName", user_elem.get("LogonName", "Unknown"))
            participants.add(sender)
            text_elem = message.find("Text")
            text = ""
            if text_elem is not None:
                text = text_elem.text or ""
            if text.strip():
                messages_list.append(self._format_message(timestamp, sender, text.strip()))
        return self._build_messaging_result_for_file(file_path, messages_list, participants)

    def _parse_msn_datetime(self, date_str: str, time_str: str) -> datetime | None:
        if not date_str and (not time_str):
            return None
        if "T" in date_str:
            try:
                parsed = datetime.fromisoformat(date_str.split(".", maxsplit=1)[0])
            except ValueError:
                parsed = None
            if parsed is not None:
                return parsed
        combined = f"{date_str} {time_str}".strip()
        msn_datetime_formats = [
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]
        return self._try_parse_datetime_formats(combined, msn_datetime_formats)
