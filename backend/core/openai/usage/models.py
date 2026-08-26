"""SoAI - Canonical OpenAI usage models [backend/core/openai/usage/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

    type CanonicalUsageSource = Literal[
        "provider_reported",
        "reconstructed_transcript",
        "aggregate_provider_reported",
        "aggregate_reconstructed_transcript",
        "aggregate_mixed",
    ]
    type ProviderUsageStatus = Literal[
        "accepted",
        "absent",
        "invalid",
        "incomplete",
        "total_mismatch",
    ]

__all__ = (
    "CanonicalUsage",
    "CanonicalUsageResolution",
    "ProviderUsageNormalization",
)


@dataclass(frozen=True, slots=True)
class CanonicalUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    usage_source: CanonicalUsageSource


@dataclass(frozen=True, slots=True)
class ProviderUsageNormalization:
    usage: CanonicalUsage | None
    status: ProviderUsageStatus


@dataclass(frozen=True, slots=True)
class CanonicalUsageResolution:
    usage: CanonicalUsage
    status: ProviderUsageStatus
