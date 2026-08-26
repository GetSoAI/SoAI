"""SoAI - Pydantic schemas for model API endpoints [backend/features/api/schemas/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.models.search_types import (
    RemoteModelSearchResultBaseModel,
    RemoteModelSearchVariantBaseModel,
)
from core.openai.modalities import get_openai_capability_taxonomy
from core.types.json import JSONValue
from core.validation.identifiers import validate_safe_identifier
from core.validation.strings import optional_trimmed_text
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "ModelAliasUpdate",
    "ModelDownloadRequest",
    "ModelEnabledUpdate",
    "ModelOpenAICapabilityOverrideUpdate",
    "ModelParametersResetRequest",
    "ModelParametersUpdate",
    "ModelVariant",
    "RemoteModelSearchResult",
    "RemoteModelSearchVariant",
    "SpeedTestMetadata",
)


class ModelAliasUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1024)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return optional_trimmed_text(
            value,
            "Display name, if provided, cannot be empty or contain only whitespace.",
        )

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> ModelAliasUpdate:
        if self.display_name is None and self.description is None:
            raise ValidationError(
                "At least one field ('display_name' or 'description') must be provided for an update.",
            )
        return self


class ModelParametersUpdate(BaseModel):
    parameters: dict[str, PydanticJSONValue]


class ModelParametersResetRequest(BaseModel):
    keys: list[str] = Field(...)

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValidationError("At least one key must be provided.")
        return values


class ModelEnabledUpdate(BaseModel):
    enabled: bool


class ModelDownloadRequest(BaseModel):
    plugin: str | None = None
    model_id: str | None = None
    universal_id: str | None = None
    quantization: str | None = None

    @model_validator(mode="before")
    @classmethod
    def check_identifiers(cls, data: JSONValue) -> JSONValue:
        if not isinstance(data, dict):
            return data
        universal_id, plugin_name, model_id = (
            data.get("universal_id"),
            data.get("plugin"),
            data.get("model_id"),
        )
        if universal_id and (plugin_name or model_id):
            raise ValidationError("Cannot provide both 'universal_id' and 'plugin'/'model_id'.")
        if not universal_id and (not (plugin_name and model_id)):
            raise ValidationError(
                "Must provide either 'universal_id' or both 'plugin' and 'model_id'.",
            )
        if (plugin_name and not model_id) or (not plugin_name and model_id):
            raise ValidationError("'plugin' and 'model_id' must be provided together.")
        return data

    @field_validator("model_id", "universal_id", "plugin")
    @classmethod
    def validate_model_id(cls, value: str | None) -> str | None:
        return validate_safe_identifier(value, "ID", 255, "^[a-zA-Z0-9/._:-]+$")

    @field_validator("quantization")
    @classmethod
    def validate_quantization(cls, value: str | None) -> str | None:
        return validate_safe_identifier(value, "Quantization", 100, "^[a-zA-Z0-9/._-]+$")


class ModelOpenAICapabilityOverrideUpdate(BaseModel):
    category: Literal[
        "endpoints",
        "image_features",
        "chat_features",
        "responses_features",
        "modalities",
    ]
    token: str = Field(..., max_length=64)
    enabled: bool

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValidationError("token is required.")
        return normalized

    @model_validator(mode="after")
    def validate_membership(self) -> ModelOpenAICapabilityOverrideUpdate:
        taxonomy = get_openai_capability_taxonomy()
        allowed = set(taxonomy.get(self.category, ()))
        if self.token not in allowed:
            raise ValidationError(f"Unknown OpenAI token '{self.token}' for {self.category}.")
        if self.category == "modalities" and self.token == "text" and self.enabled is False:
            raise ValidationError("The 'text' modality cannot be disabled.")
        return self


class SpeedTestMetadata(BaseModel):
    status: Literal["ready", "unavailable"] = Field(
        ...,
        description="State of the download speed test measurement.",
    )
    observed_at_ms: int | None = Field(
        None,
        ge=0,
        description="Epoch millisecond timestamp when the speed test completed.",
    )
    duration_ms: int | None = Field(
        None,
        ge=0,
        description="Measured duration of the speed test in milliseconds.",
    )
    bytes_downloaded: int | None = Field(
        None,
        ge=0,
        description="Number of bytes downloaded during the speed test.",
    )
    bytes_per_second: float | None = Field(
        None,
        ge=0.0,
        description="Measured throughput in bytes per second.",
    )
    estimated_ms: int | None = Field(
        None,
        ge=0,
        description="Estimated time to download the variant in milliseconds.",
    )
    base_estimated_ms: int | None = Field(
        None,
        ge=0,
        description="Raw estimate before applying load factors, in milliseconds.",
    )
    estimation_factor: float | None = Field(
        None,
        ge=0.0,
        description="Multiplier applied to the base estimate.",
    )
    size_bytes: int | None = Field(None, description="Variant size in bytes used for the estimate.")
    sample_bytes: int | None = Field(
        None,
        ge=0,
        description="Sample size exercised during the speed test.",
    )
    mode: str | None = Field(
        None,
        description="Measurement mode identifier such as disk_read or network_download.",
    )
    storage_path: str | None = Field(
        None,
        description="Source path or identifier used for the measurement.",
    )
    interface: str | None = Field(
        None,
        description="Network interface used for the measurement, if applicable.",
    )
    detail: str | None = Field(
        None,
        description="Additional context when the speed test is unavailable.",
    )


class ModelVariant(BaseModel):
    id: str = Field(
        ...,
        description="Stable variant identifier combining upstream model id and variant reference.",
    )
    name: str = Field(
        ...,
        description="Unique plugin-provided variant identifier passed to the download endpoint.",
    )
    normalized_name: str = Field(
        ...,
        description="Normalized version of the variant name, suitable for comparisons.",
    )
    description: str | None = Field(
        None,
        description="A user-friendly description of the variant.",
    )
    quantization: str | None = Field(
        None,
        description="Opaque plugin-provided quantization descriptor associated with the variant.",
    )
    size_bytes: int | None = Field(None, description="Total size of the variant payload in bytes.")
    size_gb: float | None = Field(None, description="Approximate size of the variant in gigabytes.")
    ram_required_gb: float | None = Field(
        None,
        description="Estimated combined system memory footprint (RAM plus VRAM where applicable).",
    )
    vram_required_gb: float | None = Field(
        None,
        description="Estimated VRAM needed to run this variant.",
    )
    checksum: str | None = Field(
        None,
        description="Checksum associated with the variant payload, if reported by the repository.",
    )
    family: str | None = Field(None, description="Opaque plugin-provided model family descriptor.")
    disk_fit: bool | None = Field(
        None,
        description="Whether the download is expected to fit on disk beneath the plugin's models directory.",
    )
    disk_required_gb: float | None = Field(
        None,
        description="Estimated disk space required to download this variant.",
    )
    disk_available_gb: float | None = Field(
        None,
        description="Estimated available disk space when the check was performed.",
    )
    vram_fit: bool | None = Field(
        None,
        description="Whether the variant's estimated RAM requirement fits within the detected VRAM budget.",
    )
    vram_ram_fit: bool | None = Field(
        None,
        description="Whether combined RAM and VRAM requirements fit detected system capacity.",
    )
    advisory: str | None = Field(
        None,
        description="Human-readable advisory summarizing fit checks.",
    )
    runnable: bool | None = Field(
        None,
        description="Whether the model is likely runnable on the current system.",
    )
    hardware_compatibility: str | None = Field(
        None,
        description="Hardware compatibility note for the variant (e.g., cpu_gpu or gpu_only).",
    )
    hardware_compatibility_label: str | None = Field(
        None,
        description="Display label for the hardware compatibility note.",
    )
    disk_remaining_gb: float | None = Field(
        None,
        description="Estimated disk space remaining after download completes.",
    )
    speed_test: SpeedTestMetadata | None = Field(
        None,
        description="Download speed test results for this variant.",
    )
    network_speed_test: SpeedTestMetadata | None = Field(
        None,
        description="Network speed estimate for downloading this variant.",
    )


class RemoteModelSearchVariant(RemoteModelSearchVariantBaseModel):
    extra: dict[str, PydanticJSONValue] = Field(default_factory=dict[str, PydanticJSONValue])


class RemoteModelSearchResult(RemoteModelSearchResultBaseModel):
    tags: list[str] = Field(default_factory=list[str])
    metadata: dict[str, PydanticJSONValue] = Field(default_factory=dict[str, PydanticJSONValue])
    variants: list[RemoteModelSearchVariant] = Field(default_factory=list[RemoteModelSearchVariant])
