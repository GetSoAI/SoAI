"""SoAI - Conversation message content integrity helpers [backend/database/repositories/users/message_content_integrity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

__all__ = ("build_message_content_integrity",)


def build_message_content_integrity(content_json: str) -> tuple[int, str]:
    encoded_content = content_json.encode("utf-8")
    return len(content_json), hashlib.sha256(encoded_content).hexdigest()
