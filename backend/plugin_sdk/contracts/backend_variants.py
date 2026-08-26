"""SoAI - Plugin SDK backend variant helpers [backend/plugin_sdk/contracts/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.backend_variants import (
    AUTO_BACKEND_VARIANT_ID,
    build_auto_backend_variant_option,
    normalize_backend_variant_id,
    require_backend_variant_id,
    resolve_cuda_backend_availability,
)

__all__ = (
    "AUTO_BACKEND_VARIANT_ID",
    "build_auto_backend_variant_option",
    "normalize_backend_variant_id",
    "require_backend_variant_id",
    "resolve_cuda_backend_availability",
)
