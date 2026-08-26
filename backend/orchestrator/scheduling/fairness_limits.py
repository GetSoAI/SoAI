"""SoAI - Scheduler fairness limit computation [backend/orchestrator/scheduling/fairness_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("compute_fairness_limit",)


def compute_fairness_limit(*, configured_limit: int, fair_dispatch_cap: int) -> int:
    cap = max(fair_dispatch_cap, 1)
    return min(cap, configured_limit) if configured_limit > 0 else cap
