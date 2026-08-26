"""SoAI - Reserved clone configuration staging [backend/app/config/clone_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
from typing import TYPE_CHECKING

from ruamel.yaml.comments import CommentedMap

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
)
from core.config.yaml_factory import build_roundtrip_yaml
from core.errors.exceptions import StateError
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.hardware.reservation_claims import claim_reserved_write

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict

__all__ = ("stage_cloned_config",)


def _stage_cloned_config(
    config_path: str,
    data: JSONDict,
    reservation: DiskSpaceReservationLeaseProtocol,
    maximum_bytes: int,
) -> None:
    stream = io.StringIO()
    build_roundtrip_yaml().dump(CommentedMap(data), stream)
    content = stream.getvalue()
    encoded_size = len(content.encode("utf-8"))
    if encoded_size <= 0 or encoded_size > maximum_bytes:
        raise StateError("Staged clone configuration exceeded reserved capacity.")
    with claim_reserved_write(reservation, size_bytes=encoded_size):
        atomic_create_text_content_exclusive(
            config_path,
            content,
            encoding="utf-8",
            file_mode=0o600,
            fsync_parent_directory=True,
        )


async def stage_cloned_config(
    config_path: str,
    data: JSONDict,
    reservation: DiskSpaceReservationLeaseProtocol,
    *,
    maximum_bytes: int,
) -> None:
    await uncancel_and_wait(
        asyncio.to_thread(
            _stage_cloned_config,
            config_path,
            data,
            reservation,
            maximum_bytes,
        )
    )
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError
