"""SoAI - CORS state configuration logic for API lifecycle [backend/features/api/lifecycle/cors_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern

from core.errors.exceptions import ValidationError
from features.api.api_cors_runtime import CORSMiddlewareConfig

__all__ = (
    "CORSStateConfiguration",
    "configure_cors_state",
)


@dataclass(frozen=True, slots=True)
class CORSStateConfiguration:
    cors_config: CORSMiddlewareConfig
    cors_trusted_origins: tuple[str, ...]
    cors_origin_regex: Pattern[str] | None
    cors_max_age: int


def configure_cors_state(
    cors_config: CORSMiddlewareConfig,
) -> CORSStateConfiguration:
    allow_origins_raw = cors_config.get("allow_origins", [])
    if isinstance(allow_origins_raw, list | tuple | set):
        cors_trusted_origins = tuple(
            str(origin).strip() for origin in allow_origins_raw if str(origin).strip()
        )
    else:
        cors_trusted_origins = ()
    origin_regex_text = cors_config.get("allow_origin_regex")
    cors_origin_regex: Pattern[str] | None = None
    if origin_regex_text is not None:
        if not isinstance(origin_regex_text, str):
            raise ValidationError(
                "CORS allow_origin_regex must be a string.",
                details={"actual_type": type(origin_regex_text).__name__},
            )
        try:
            cors_origin_regex = re.compile(origin_regex_text)
        except re.error as exception:
            raise ValidationError(
                "CORS allow_origin_regex is invalid.",
                cause=exception,
                details={"pattern": origin_regex_text},
            ) from exception
    cors_max_age = cors_config.get("max_age", 3600)
    if not isinstance(cors_max_age, int):
        cors_max_age = 3600
    return CORSStateConfiguration(
        cors_config=cors_config,
        cors_trusted_origins=cors_trusted_origins,
        cors_origin_regex=cors_origin_regex,
        cors_max_age=cors_max_age,
    )
