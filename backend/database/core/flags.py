"""SoAI - Database feature flags and limits [backend/database/core/flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "FEATURE_AUTH",
    "FEATURE_METRICS",
    "FEATURE_PROMPTS",
    "OPENAI_API_KEY_LIMIT",
)

FEATURE_AUTH = "auth"
FEATURE_PROMPTS = "prompts"
FEATURE_METRICS = "metrics"
OPENAI_API_KEY_LIMIT = 1000
