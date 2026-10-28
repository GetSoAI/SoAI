"""SoAI - Upstream component telemetry opt-out environment [backend/core/bootstrap/upstream_telemetry_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = (
    "UPSTREAM_TELEMETRY_OPT_OUTS",
    "apply_upstream_telemetry_opt_outs",
)

UPSTREAM_TELEMETRY_OPT_OUTS: tuple[tuple[str, str], ...] = (
    ("DO_NOT_TRACK", "1"),
    ("VLLM_NO_USAGE_STATS", "1"),
    ("VLLM_DO_NOT_TRACK", "1"),
    ("HF_HUB_DISABLE_TELEMETRY", "1"),
    ("HF_HUB_DISABLE_UPDATE_CHECK", "1"),
    ("PIP_DISABLE_PIP_VERSION_CHECK", "1"),
    ("ORT_DISABLE_TELEMETRY", "1"),
)


def apply_upstream_telemetry_opt_outs() -> None:
    os.environ.update(UPSTREAM_TELEMETRY_OPT_OUTS)
