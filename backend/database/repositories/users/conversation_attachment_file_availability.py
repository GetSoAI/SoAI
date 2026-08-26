"""SoAI - Conversation attachment managed file availability checks [backend/database/repositories/users/conversation_attachment_file_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from database.core.query_execution import sync_fetch_one_as_dict

__all__ = ("sync_require_attachment_file_available",)


def _close_managed_descriptor(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError as exception:
        raise ConflictError("Attachment file descriptor could not be closed.") from exception


def sync_require_attachment_file_available(
    conn: sqlite3.Connection,
    *,
    file_id: str,
    user_id: int,
    size_bytes: int,
    storage_root: str | None,
) -> None:
    if storage_root is None:
        raise ConflictError("Attachment file storage root is not available.")
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT purpose, api_key_id, file_path, size_bytes, content_sha256
            FROM files_catalog
            WHERE id = ? AND user_id IS ? AND api_key_id IS NULL
            """,
            (file_id, user_id),
        ),
    )
    if row is None:
        raise ConflictError("Attachment file is not available.")
    if row.get("purpose") != WEBUI_CHAT_ATTACHMENT_PURPOSE:
        raise ConflictError("Attachment file purpose is invalid.")
    if row.get("api_key_id") is not None:
        raise ConflictError("Attachment file ownership is invalid.")
    if row.get("size_bytes") != size_bytes:
        raise ConflictError("Attachment file size changed before message write.")
    raw_content_sha256 = row.get("content_sha256")
    if not isinstance(raw_content_sha256, str):
        raise ConflictError("Attachment file hash is invalid.")
    try:
        content_sha256 = require_canonical_sha256_hexdigest(
            raw_content_sha256,
            label="Attachment file hash",
        )
    except StateError as exception:
        raise ConflictError("Attachment file hash is invalid.") from exception
    file_path = row.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise ConflictError("Attachment file path is invalid.")
    try:
        managed_file = open_managed_file_descriptor(storage_root, file_path)
    except FileStorageSecurityError as exception:
        raise ConflictError("Attachment file is not available.") from exception
    try:
        if managed_file.size_bytes != size_bytes:
            raise ConflictError("Attachment file size changed before message write.")
        try:
            content_hash = hash_descriptor_content(managed_file.descriptor)
        except ValidationError as exception:
            raise ConflictError("Attachment file content could not be verified.") from exception
        if content_hash.size_bytes != size_bytes or content_hash.sha256_hex != content_sha256:
            raise ConflictError("Attachment file content changed before message write.")
    finally:
        _close_managed_descriptor(managed_file.descriptor)
