"""SoAI - Writer-owned storage reservation contracts [backend/core/database/write_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.di.validation import require_dependencies
from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol
from core.validation.requirements import require_non_negative_exact_int

__all__ = ("DatabaseWriteStorage",)


@dataclass(frozen=True, slots=True)
class DatabaseWriteStorage:
    provider: DiskSpaceReservationProviderProtocol
    required_bytes: int
    completed: threading.Event = field(default_factory=threading.Event, init=False, compare=False)

    def __post_init__(self) -> None:
        require_dependencies(owner="DatabaseWriteStorage", provider=self.provider)
        require_non_negative_exact_int(
            self.required_bytes,
            type_message="Database write storage budget must be an integer.",
            range_message="Database write storage budget must not be negative.",
        )
