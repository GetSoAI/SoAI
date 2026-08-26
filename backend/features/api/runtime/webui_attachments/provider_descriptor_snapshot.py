"""SoAI - Immutable provider descriptor snapshots for WebUI attachments [backend/features/api/runtime/webui_attachments/provider_descriptor_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.attachments.attachment_parse_temp_copy import (
    copy_attachment_descriptor_to_temp_path,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.logging.trace import get_logger

__all__ = (
    "ProviderDescriptorSnapshot",
    "close_provider_descriptor_snapshot",
    "load_provider_descriptor_snapshot",
)

LOGGER_NAME = "SoAI.features.api.provider_descriptor_snapshot"
OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT = "webui.attachments.provider_descriptor_snapshot"


@dataclass(frozen=True, slots=True)
class ProviderDescriptorSnapshot:
    descriptor: int
    temp_path: str


def _remove_temp_path(temp_path: str) -> None:
    try:
        os.remove(temp_path)
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to remove temporary WebUI provider snapshot.",
            operation=OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT,
            details={"temp_path": temp_path},
            level="debug",
        )


def _close_descriptor(descriptor: int, *, temp_path: str) -> None:
    try:
        os.close(descriptor)
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to close WebUI provider snapshot.",
            operation=OPERATION_PROVIDER_DESCRIPTOR_SNAPSHOT,
            details={"temp_path": temp_path},
            level="debug",
        )


def close_provider_descriptor_snapshot(snapshot: ProviderDescriptorSnapshot) -> None:
    _close_descriptor(snapshot.descriptor, temp_path=snapshot.temp_path)
    _remove_temp_path(snapshot.temp_path)


def load_provider_descriptor_snapshot(
    *,
    source_descriptor: int,
    filename: str,
    expected_size_bytes: int,
    expected_sha256: str,
) -> ProviderDescriptorSnapshot | None:
    try:
        temp_path = copy_attachment_descriptor_to_temp_path(
            descriptor=source_descriptor,
            filename=filename,
        )
    except OSError:
        return None
    try:
        snapshot_descriptor = os.open(temp_path, os.O_RDONLY)
        try:
            content_hash = hash_descriptor_content(snapshot_descriptor)
        except ValidationError:
            _close_descriptor(snapshot_descriptor, temp_path=temp_path)
            _remove_temp_path(temp_path)
            return None
        if content_hash.size_bytes != expected_size_bytes:
            _close_descriptor(snapshot_descriptor, temp_path=temp_path)
            _remove_temp_path(temp_path)
            return None
        if content_hash.sha256_hex != expected_sha256:
            _close_descriptor(snapshot_descriptor, temp_path=temp_path)
            _remove_temp_path(temp_path)
            return None
        return ProviderDescriptorSnapshot(descriptor=snapshot_descriptor, temp_path=temp_path)
    except OSError:
        _remove_temp_path(temp_path)
        return None
