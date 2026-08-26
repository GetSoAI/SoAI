"""SoAI - Plugin/provider schemas [backend/features/api/schemas/plugins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.types.json import JSONValue
from core.validation.string_mappings import validate_string_mapping
from core.validation.strings import optional_trimmed_text
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "ClonePluginRequest",
    "ExternalProviderCreate",
    "ExternalProviderUpdate",
    "InstallPluginBackendRequest",
    "PluginCompatibilityOverrideRequest",
    "PluginDownloadRequest",
    "ProviderNameModel",
    "RemovePluginBackendRequest",
    "UpdatePluginBackendRequest",
)


class ExactRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PluginDownloadRequest(ExactRequestModel):
    url: AnyHttpUrl


class PluginCompatibilityOverrideRequest(ExactRequestModel):
    override: bool


class ClonePluginRequest(ExactRequestModel):
    target_name: str | None = None
    clone_models: bool
    field_overrides: dict[str, PydanticJSONValue] | None = None
    task_id: str = Field(description="Client-provided durable mutation request ID.")

    @field_validator("target_name")
    @classmethod
    def validate_target_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_portable_plugin_identifier(value, field_name="target_name")

    @field_validator("task_id")
    @classmethod
    def validate_task_id_field(cls, value: str) -> str:
        return require_mutation_request_id(value)


class BackendVariantRequest(ExactRequestModel):
    backend_variant_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, value: JSONValue) -> JSONValue:
        if isinstance(value, dict) and "backend_variant_id" in value:
            backend_variant_id = value["backend_variant_id"]
            if not isinstance(backend_variant_id, str) or not backend_variant_id.strip():
                raise ValidationError(
                    "backend_variant_id must be a non-empty string when provided."
                )
        return value

    @field_validator("backend_variant_id")
    @classmethod
    def normalize_backend_variant_id(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class InstallPluginBackendRequest(BackendVariantRequest): ...


class UpdatePluginBackendRequest(BackendVariantRequest): ...


class RemovePluginBackendRequest(ExactRequestModel):
    delete_models: bool


class ProviderNameModel(ExactRequestModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def validate_provider_name(cls, value: str | None) -> str | None:
        return optional_trimmed_text(value, "Provider name, if provided, cannot be empty.")


class ExternalProviderCreate(ProviderNameModel):
    api_url: AnyHttpUrl
    api_key: str | None = None
    models_filter: list[str] | None = None
    context_window_tokens: int | None = Field(default=None, gt=0)
    extra_headers: dict[str, str] | None = None
    extra_query_params: dict[str, str] | None = None

    @field_validator("extra_headers", "extra_query_params", mode="before")
    @classmethod
    def validate_mappings(cls, value: JSONValue) -> dict[str, str] | None:
        return validate_string_mapping(value)


class ExternalProviderUpdate(ProviderNameModel):
    api_url: AnyHttpUrl | None = None
    api_key: str | None = None
    models_filter: list[str] | None = None
    context_window_tokens: int | None = Field(default=None, gt=0)
    extra_headers: dict[str, str] | None = None
    extra_query_params: dict[str, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_nonclearable_nulls(cls, value: JSONValue) -> JSONValue:
        if isinstance(value, dict):
            for field_name in ("name", "api_url"):
                if field_name in value and value[field_name] is None:
                    raise ValidationError(f"{field_name} cannot be null.")
        return value

    @field_validator("extra_headers", "extra_query_params", mode="before")
    @classmethod
    def validate_mappings(cls, value: JSONValue) -> dict[str, str] | None:
        return validate_string_mapping(value)
