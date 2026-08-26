"""SoAI - API key-related schemas [backend/features/api/schemas/api_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, StrictInt, field_validator

from core.auth.auth_decisions import resolve_openai_api_key_action_set
from core.quotas.api_key_quota_windows import normalize_api_key_quota_mode
from core.validation.strings import optional_trimmed_text, require_trimmed_text
from features.api.schemas.shared_validation import require_positive_optional_schema_int

__all__ = (
    "OpenAIAPIKeyCreatePayload",
    "OpenAIAPIKeyQuotaHourlyPayload",
    "OpenAIAPIKeyQuotaLimitPayload",
    "OpenAIAPIKeyQuotaUpdatePayload",
    "SearchProviderApiKeyUpdate",
)


def _require_positive_optional_int(
    value: StrictInt | None,
    *,
    error_message: str,
) -> StrictInt | None:
    require_positive_optional_schema_int(value, error_message=error_message)
    return value


class OpenAIAPIKeyCreatePayload(BaseModel):
    label: str | None = None
    scopes: list[str] | None = None
    expires_in_days: StrictInt | None = None
    expires_at_ms: StrictInt | None = None
    rotation_reminder_in_days: StrictInt | None = None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        return optional_trimmed_text(value, "Label cannot be empty.")

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned: list[str] = []
        for entry in values:
            text = require_trimmed_text(str(entry or ""), "Scopes cannot contain empty entries.")
            cleaned.append(text)
        resolved = resolve_openai_api_key_action_set(tuple(cleaned))
        return sorted(action.value for action in resolved)

    @field_validator("expires_in_days", "rotation_reminder_in_days")
    @classmethod
    def validate_positive_day_window(cls, value: StrictInt | None) -> StrictInt | None:
        return _require_positive_optional_int(
            value,
            error_message="Day intervals must be greater than zero.",
        )

    @field_validator("expires_at_ms")
    @classmethod
    def validate_expires_at(cls, value: StrictInt | None) -> StrictInt | None:
        return _require_positive_optional_int(
            value,
            error_message="Expiration timestamps must be positive.",
        )


class SearchProviderApiKeyUpdate(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        return require_trimmed_text(value, "API key cannot be empty.")


class OpenAIAPIKeyQuotaLimitPayload(BaseModel):
    limit_units: StrictInt | None = None

    @field_validator("limit_units")
    @classmethod
    def validate_limit_units(cls, value: StrictInt | None) -> StrictInt | None:
        return _require_positive_optional_int(
            value,
            error_message="limit_units must be greater than zero.",
        )


class OpenAIAPIKeyQuotaHourlyPayload(BaseModel):
    limit_units: StrictInt | None = None
    window_hours: StrictInt | None = None

    @field_validator("limit_units")
    @classmethod
    def validate_limit_units(cls, value: StrictInt | None) -> StrictInt | None:
        return _require_positive_optional_int(
            value,
            error_message="hourly.limit_units must be greater than zero.",
        )

    @field_validator("window_hours")
    @classmethod
    def validate_window_hours(cls, value: StrictInt | None) -> StrictInt | None:
        return _require_positive_optional_int(
            value,
            error_message="hourly.window_hours must be greater than zero.",
        )


class OpenAIAPIKeyQuotaUpdatePayload(BaseModel):
    mode: str
    hourly: OpenAIAPIKeyQuotaHourlyPayload | None = None
    daily: OpenAIAPIKeyQuotaLimitPayload | None = None
    weekly: OpenAIAPIKeyQuotaLimitPayload | None = None
    monthly: OpenAIAPIKeyQuotaLimitPayload | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        return normalize_api_key_quota_mode(
            require_trimmed_text(value, "mode cannot be empty."),
            empty_message="mode cannot be empty.",
        )
