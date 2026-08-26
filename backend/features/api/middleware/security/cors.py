"""SoAI - API security CORS helpers [backend/features/api/middleware/security/cors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = ("normalize_cors_allowed_origins",)


def normalize_cors_allowed_origins(
    config_obj: ConfigProtocol,
) -> tuple[tuple[str, ...], bool]:
    origins_raw = config_obj.get("SERVER.HTTP.CORS.ALLOWED_ORIGINS", [])
    if origins_raw is None:
        return ((), False)
    if isinstance(origins_raw, str):
        origins_sequence: Iterable[ConfigValue] = [origins_raw]
    elif isinstance(origins_raw, list | tuple):
        origins_sequence = origins_raw
    else:
        raise ValidationError(
            "SERVER.HTTP.CORS.ALLOWED_ORIGINS must be a list, tuple, string wildcard, or null.",
        )
    normalized: list[str] = []
    has_wildcard = False
    for origin in origins_sequence:
        if not isinstance(origin, str):
            raise ValidationError("SERVER.HTTP.CORS.ALLOWED_ORIGINS entries must be strings.")
        text = origin.strip()
        if not text:
            continue
        if text == "*":
            has_wildcard = True
        normalized.append(text)
    return (tuple(dict.fromkeys(normalized)), has_wildcard)
