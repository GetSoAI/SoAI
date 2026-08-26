"""SoAI - Database feature gate for configuration toggles [backend/database/core/feature_gate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import NotFoundError
from database.core.flags import FEATURE_AUTH, FEATURE_METRICS, FEATURE_PROMPTS

__all__ = ("DatabaseFeatureGate",)

_ENABLED_FEATURES: frozenset[str] = frozenset(
    {
        FEATURE_AUTH,
        FEATURE_METRICS,
        FEATURE_PROMPTS,
    },
)


class DatabaseFeatureGate:
    def is_enabled(self, feature: str) -> bool:
        normalized_feature = feature.strip()
        if not normalized_feature:
            return False
        if normalized_feature not in _ENABLED_FEATURES:
            raise NotFoundError(f"Unknown feature flag '{feature}'.")
        return True

    def ensure_feature_enabled(self, feature: str) -> None:
        self.is_enabled(feature)
