"""SoAI - Model download finalization outcomes [backend/plugins/manager/transfer_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = (
    "ModelDiscoveryQueueStatus",
    "ModelDownloadFinalization",
)


class ModelDiscoveryQueueStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class ModelDownloadFinalization:
    discovery_status: ModelDiscoveryQueueStatus
