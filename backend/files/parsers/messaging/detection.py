"""SoAI - Messaging export format detection [backend/files/parsers/messaging/detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
import zipfile

from defusedxml import ElementTree

from core.errors.exceptions import ValidationError
from core.files.extensions.messaging import (
    MESSAGING_PLATFORM_IDENTIFIERS,
    PLATFORM_DISCORD,
    PLATFORM_FACEBOOK,
    PLATFORM_MSN,
    PLATFORM_SIGNAL,
    PLATFORM_TELEGRAM,
    PLATFORM_WHATSAPP,
    get_messaging_platform_extension_aliases,
)
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_value

__all__ = ("detect_messaging_platform",)


def detect_messaging_platform(file_path: str) -> str | None:
    ext = os.path.splitext(file_path)[1].lower()
    normalized_extension = ext.removeprefix(".")
    if normalized_extension in MESSAGING_PLATFORM_IDENTIFIERS:
        return normalized_extension
    platform_from_extension = get_messaging_platform_extension_aliases().get(normalized_extension)
    if platform_from_extension is not None:
        return platform_from_extension
    if ext == ".zip":
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                if any("_chat.txt" in name.lower() or "whatsapp" in name.lower() for name in names):
                    return PLATFORM_WHATSAPP
        except zipfile.BadZipFile:
            return None
        return None
    if ext == ".xml":
        try:
            tree = ElementTree.parse(file_path)
            root = tree.getroot()
            if root is None:
                return None
            if root.tag == "Log" or root.find(".//Log") is not None:
                if root.find(".//Message") is not None or (
                    root.tag == "Log" and list(root.iter("Message"))
                ):
                    return PLATFORM_MSN
        except ElementTree.ParseError:
            return None
        return None
    if ext == ".json":
        try:
            with open_text(file_path, encoding="utf-8") as file_handle:
                data = parse_json_value(file_handle.read(), field="messaging export")
            if isinstance(data, dict):
                raw_messages = data.get("messages")
                messages_for_detection = raw_messages if isinstance(raw_messages, list) else []
                if "chats" in data and isinstance(data.get("chats"), dict):
                    return PLATFORM_TELEGRAM
                if "messages" in data:
                    if data.get("guild") or data.get("channel"):
                        return PLATFORM_DISCORD
                    if "participants" in data and isinstance(raw_messages, list):
                        messages = messages_for_detection[:5]
                        if any(
                            isinstance(message, dict) and "sender_name" in message
                            for message in messages
                        ):
                            return PLATFORM_FACEBOOK
                    messages = messages_for_detection[:5]
                    if any(
                        isinstance(message, dict) and "from_id" in message for message in messages
                    ):
                        return PLATFORM_TELEGRAM
        except (OSError, ValidationError):
            return None
        return None
    if ext == ".txt":
        try:
            with open_text(file_path, encoding="utf-8", errors="replace") as file_handle:
                sample = file_handle.read(2000)
            whatsapp_patterns = [
                "^\\[?\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4},?\\s*\\d{1,2}:\\d{2}",
                "\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4},?\\s*\\d{1,2}:\\d{2}(?::\\d{2})?\\s*(?:AM|PM)?\\s*-\\s*[^:]+:",
            ]
            for pattern in whatsapp_patterns:
                if re.search(pattern, sample, re.MULTILINE | re.IGNORECASE):
                    return PLATFORM_WHATSAPP
        except OSError:
            return None
        return None
    if ext in (".html", ".htm"):
        try:
            with open_text(file_path, encoding="utf-8", errors="replace") as file_handle:
                sample = file_handle.read(5000)
            if "signal" in sample.lower() or 'class="message"' in sample:
                return PLATFORM_SIGNAL
        except OSError:
            return None
        return None
    if ext == ".csv":
        try:
            with open_text(file_path, encoding="utf-8", errors="replace") as file_handle:
                header = file_handle.readline().lower()
            if any(col in header for col in ["sender", "body", "message", "timestamp"]):
                return PLATFORM_SIGNAL
        except OSError:
            return None
        return None
    return None
