"""SoAI - Chroma collection metadata disk reservations [backend/mcp/storage/chroma_collection_reservation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.hardware.reservation_claims import claim_reserved_write

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict

__all__ = ("reserve_chroma_collection_metadata",)

_CHROMA_COLLECTION_METADATA_RESERVATION_BYTES = MIB_BYTES


@contextmanager
def reserve_chroma_collection_metadata(
    storage_manager: StorageManagerProtocol,
    *,
    chroma_path: str,
    operation: str,
    details: JSONDict,
) -> Generator[None]:
    with (
        storage_manager.reserve_disk_space(
            path=chroma_path,
            required_bytes=_CHROMA_COLLECTION_METADATA_RESERVATION_BYTES,
            operation=operation,
            details=details,
        ) as reservation,
        claim_reserved_write(
            reservation,
            size_bytes=_CHROMA_COLLECTION_METADATA_RESERVATION_BYTES,
        ),
    ):
        yield
