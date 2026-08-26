"""SoAI - Upload limit configuration resolution [backend/core/config/upload_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES, mib_to_bytes
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError, ValidationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "UploadLimitType",
    "resolve_upload_limit_bytes",
)


class UploadLimitType(Enum):
    FILE = "file"
    AUDIO = "audio"
    IMAGE = "image"


def _resolve_upload_limit_config(limit_type: UploadLimitType) -> tuple[str, int, str]:
    match limit_type:
        case UploadLimitType.FILE:
            return (
                "API.OPENAI.MAX_FILE_UPLOAD_MB",
                250,
                "config.upload_limits.resolve_file_upload_limit_bytes",
            )
        case UploadLimitType.AUDIO:
            return (
                "API.OPENAI.MAX_AUDIO_UPLOAD_MB",
                25,
                "config.upload_limits.resolve_audio_upload_limit_bytes",
            )
        case UploadLimitType.IMAGE:
            return (
                "API.OPENAI.MAX_IMAGE_UPLOAD_MB",
                25,
                "config.upload_limits.resolve_image_upload_limit_bytes",
            )
    raise ValidationError("Unsupported upload limit type.")


def _coerce_upload_limit_mb(
    raw_limit: ConfigValue | None,
    *,
    upload_label: str,
    config_key: str,
    operation: str,
) -> float:
    if isinstance(raw_limit, bool):
        raise ConfigurationError(
            (
                f"Invalid {upload_label} upload limit type in configuration: expected "
                "int, float, or str, got bool."
            ),
            operation=operation,
            details={
                "raw_limit": str(raw_limit),
                "type": "bool",
                "config_key": config_key,
            },
        )
    if isinstance(raw_limit, int | float):
        try:
            return float(raw_limit)
        except OverflowError as exception:
            raise ConfigurationError(
                (
                    f"Invalid {upload_label} upload limit in configuration: "
                    f"'{raw_limit}' is too large."
                ),
                operation=operation,
                details={"raw_limit": str(raw_limit), "config_key": config_key},
                cause=exception,
            ) from exception
    if isinstance(raw_limit, str):
        try:
            return float(raw_limit)
        except ValueError as exception:
            raise ConfigurationError(
                (
                    f"Invalid {upload_label} upload limit in configuration: "
                    f"'{raw_limit}' is not a valid number."
                ),
                operation=operation,
                details={"raw_limit": raw_limit, "config_key": config_key},
                cause=exception,
            ) from exception
    raise ConfigurationError(
        (
            f"Invalid {upload_label} upload limit type in configuration: expected "
            f"int, float, or str, got {type(raw_limit).__name__}."
        ),
        operation=operation,
        details={
            "raw_limit": str(raw_limit),
            "type": type(raw_limit).__name__,
            "config_key": config_key,
        },
    )


def resolve_upload_limit_bytes(
    config_obj: ConfigProtocol | Mapping[str, ConfigValue],
    limit_type: UploadLimitType,
    *,
    default_mb: int | None = None,
) -> int:
    if not isinstance(limit_type, UploadLimitType):
        raise ValidationError("Upload limit type must be an UploadLimitType instance.")
    config_key, type_default_mb, operation = _resolve_upload_limit_config(limit_type)
    upload_label = limit_type.value
    resolved_default_mb = default_mb if default_mb is not None else type_default_mb
    if (
        isinstance(resolved_default_mb, bool)
        or not isinstance(resolved_default_mb, int)
        or resolved_default_mb <= 0
    ):
        raise ValidationError("default_mb must be a positive integer.")
    raw_limit = config_obj.get(config_key, resolved_default_mb)
    limit_value = _coerce_upload_limit_mb(
        raw_limit,
        upload_label=upload_label,
        config_key=config_key,
        operation=operation,
    )
    if not math.isfinite(limit_value):
        raise ConfigurationError(
            (
                f"Invalid {upload_label} upload limit in configuration: "
                f"'{raw_limit}' is not finite."
            ),
            operation=operation,
            details={"raw_limit": str(raw_limit), "config_key": config_key},
        )
    if limit_value <= 0:
        raise ConfigurationError(
            f"{upload_label.capitalize()} upload limit must be positive, got {limit_value} MB.",
            operation=operation,
            details={"limit_value": limit_value, "config_key": config_key},
        )
    if not math.isfinite(limit_value * MIB_BYTES):
        raise ConfigurationError(
            (
                f"Invalid {upload_label} upload limit in configuration: "
                f"'{raw_limit}' is too large."
            ),
            operation=operation,
            details={"raw_limit": str(raw_limit), "config_key": config_key},
        )
    return mib_to_bytes(limit_value)
