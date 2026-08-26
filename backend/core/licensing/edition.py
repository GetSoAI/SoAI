"""SoAI - Licensing edition validation [backend/core/licensing/edition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError


def require_licensing_edition(edition: str) -> str:
    if edition not in {"soai-core", "soai-os"}:
        raise ValidationError("Licensing edition is invalid.")
    return edition


__all__ = ("require_licensing_edition",)
