"""SoAI - Signal export parsing [backend/files/parsers/messaging/signal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from typing import override

from core.errors.exceptions import ValidationError
from core.files.types import ParsedDocument
from core.filesystem.open_files import open_text
from files.parsers.messaging.messaging_parser_base import MessagingParserBase

__all__ = ("SignalParser",)


class SignalParser(MessagingParserBase):
    platform_name = "Signal"

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            return self._parse_csv(file_path)
        if ext in (".html", ".htm"):
            return self._parse_html(file_path)
        raise ValidationError(f"Unsupported Signal export format: {ext}")

    def _parse_csv(self, file_path: str) -> ParsedDocument:
        messages_list, participants = self._init_message_context()
        with open_text(file_path, encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                sender = row.get("sender", row.get("from", row.get("name", "Unknown")))
                if sender:
                    participants.add(sender)
                timestamp_str = row.get("timestamp", row.get("date", row.get("time", "")))
                timestamp = self._parse_timestamp(timestamp_str)
                body = row.get("body", row.get("message", row.get("text", "")))
                if body:
                    messages_list.append(self._format_message(timestamp, sender, body))
        return self._build_messaging_result_for_file(file_path, messages_list, participants)

    def _parse_html(self, file_path: str) -> ParsedDocument:
        with open_text(file_path, encoding="utf-8") as file_handle:
            html_content = file_handle.read()
        messages_list, participants = self._init_message_context()
        message_pattern = re.compile(
            '<div[^>]*class="[^"]*message[^"]*"[^>]*>.*?(?:<span[^>]*class="[^"]*(?:sender|name|author)[^"]*"[^>]*>([^<]+)</span>)?.*?(?:<span[^>]*class="[^"]*(?:time|date|timestamp)[^"]*"[^>]*>([^<]+)</span>)?.*?(?:<(?:div|p|span)[^>]*class="[^"]*(?:body|text|content)[^"]*"[^>]*>([^<]+)</(?:div|p|span)>)?',
            re.DOTALL | re.IGNORECASE,
        )
        for match in message_pattern.finditer(html_content):
            sender = match.group(1) or "Unknown"
            timestamp_str = match.group(2) or ""
            body = match.group(3) or ""
            if sender:
                participants.add(sender)
            timestamp = self._parse_timestamp(timestamp_str)
            if body.strip():
                messages_list.append(self._format_message(timestamp, sender, body.strip()))
        if not messages_list:
            text_content = re.sub("<[^>]+>", " ", html_content)
            text_content = re.sub("\\s+", " ", text_content).strip()
            if text_content:
                messages_list.append(text_content[:10000])
        return self._build_messaging_result_for_file(file_path, messages_list, participants)

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        signal_timestamp_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d %b %Y %H:%M",
            "%b %d, %Y %H:%M",
        ]
        return self._try_parse_datetime_formats(ts_str, signal_timestamp_formats)
