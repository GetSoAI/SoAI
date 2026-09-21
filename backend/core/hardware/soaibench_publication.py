"""SoAI - SoAIBench publication persistence records [backend/core/hardware/soaibench_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.types.json import JSONDict

__all__ = ("SoAIBenchPublicationRecord",)


@dataclass(frozen=True, slots=True)
class SoAIBenchPublicationRecord:
    run_id: str
    created_by_user_id: int
    installation_id: str
    canonical_submission_json: str
    state: Literal["prepared", "published"]
    prepared_at_ms: int
    published_at_ms: int | None
    receipt: JSONDict | None
