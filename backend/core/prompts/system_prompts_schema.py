"""SoAI - System prompts catalog JSON schema V1 [backend/core/prompts/system_prompts_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import string
from importlib import resources
from typing import Annotated, Literal

import pydantic_core
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.meta.soai_v1_contract import CORE_SYSTEM_PROMPTS_CATALOG_SCHEMA_VERSION
from core.prompts.migrations.runner import upgrade_system_prompts_payload_to_current
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONValue, is_str_list

__all__ = (
    "ModeTemplatePromptEntryV1",
    "SystemPromptEntryV1",
    "SystemPromptTemplateEntryV1",
    "SystemPromptsPayloadV1",
    "TextPromptEntryV1",
    "TextPromptTemplateEntryV1",
    "load_system_prompts_payload_v1",
)

LOGGER_NAME = "SoAI.core.prompts.system_prompts_schema"


def _coerce_text_value(value: JSONValue, *, label: str) -> str:
    if isinstance(value, str):
        return value
    if is_str_list(value):
        return "\n".join([line.rstrip("\n") for line in value])
    raise ValidationError(f"{label} must be a string or a list of strings.")


def _normalize_placeholder_list(placeholders_raw: list[str], *, label: str) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in placeholders_raw if item.strip())
    if not normalized:
        raise ValidationError(f"{label} must not be empty.")
    return tuple(sorted(set(normalized)))


def _validate_placeholders(*, template: str, placeholders: tuple[str, ...], label: str) -> None:
    observed_fields: set[str] = set()
    formatter = string.Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if field_name is None:
            continue
        if not re.fullmatch(r"[A-Z0-9_]+", field_name):
            raise ValidationError(
                f"{label} contains invalid placeholder {field_name!r}. Escape literal braces with '{{{{' and '}}}}'.",
            )
        observed_fields.add(field_name)
    observed = sorted(observed_fields)
    expected = list(placeholders)
    if observed != expected:
        raise ValidationError(
            f"{label} placeholders mismatch. expected={expected} observed={observed}",
        )


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemPromptEntryV1(_StrictModel):
    type: Literal["system"]
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content(cls, value: JSONValue) -> str:
        return _coerce_text_value(value, label="prompt.content").strip()


class TextPromptEntryV1(_StrictModel):
    type: Literal["text"]
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content(cls, value: JSONValue) -> str:
        return _coerce_text_value(value, label="prompt.content").strip()


class ModeTemplatePromptEntryV1(_StrictModel):
    type: Literal["mode_template"]
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content(cls, value: JSONValue) -> str:
        return _coerce_text_value(value, label="prompt.content").strip()


class SystemPromptTemplateEntryV1(_StrictModel):
    type: Literal["system_template"]
    marker: str
    placeholders: tuple[str, ...]
    template: str

    @field_validator("marker", mode="before")
    @classmethod
    def normalize_marker(cls, value: JSONValue) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("prompt.marker must be a non-empty string.")
        return value.strip()

    @field_validator("placeholders", mode="before")
    @classmethod
    def coerce_placeholders(cls, value: JSONValue) -> tuple[str, ...]:
        if not is_str_list(value):
            raise ValidationError("prompt.placeholders must be a list of strings.")
        return _normalize_placeholder_list(list(value), label="prompt.placeholders")

    @field_validator("template", mode="before")
    @classmethod
    def coerce_template(cls, value: JSONValue) -> str:
        return _coerce_text_value(value, label="prompt.template").rstrip()

    @model_validator(mode="after")
    def validate_template(self) -> SystemPromptTemplateEntryV1:
        if not self.template:
            raise ValidationError("prompt.template must be a non-empty string.")
        first_line = self.template.splitlines()[0] if self.template.splitlines() else ""
        if self.marker not in first_line:
            raise ValidationError(f"prompt.template must start with marker {self.marker!r}.")
        _validate_placeholders(
            template=self.template,
            placeholders=self.placeholders,
            label="prompt.template",
        )
        return self


class TextPromptTemplateEntryV1(_StrictModel):
    type: Literal["text_template"]
    placeholders: tuple[str, ...]
    template: str

    @field_validator("placeholders", mode="before")
    @classmethod
    def coerce_placeholders(cls, value: JSONValue) -> tuple[str, ...]:
        if not is_str_list(value):
            raise ValidationError("prompt.placeholders must be a list of strings.")
        return _normalize_placeholder_list(list(value), label="prompt.placeholders")

    @field_validator("template", mode="before")
    @classmethod
    def coerce_template(cls, value: JSONValue) -> str:
        return _coerce_text_value(value, label="prompt.template").rstrip()

    @model_validator(mode="after")
    def validate_template(self) -> TextPromptTemplateEntryV1:
        if not self.template:
            raise ValidationError("prompt.template must be a non-empty string.")
        _validate_placeholders(
            template=self.template,
            placeholders=self.placeholders,
            label="prompt.template",
        )
        return self


class SystemPromptsPayloadV1(_StrictModel):
    schema_version: int
    prompts: dict[
        str,
        Annotated[
            SystemPromptTemplateEntryV1
            | TextPromptTemplateEntryV1
            | ModeTemplatePromptEntryV1
            | SystemPromptEntryV1
            | TextPromptEntryV1,
            Field(discriminator="type"),
        ],
    ]

    @model_validator(mode="after")
    def validate_version(self) -> SystemPromptsPayloadV1:
        if self.schema_version != CORE_SYSTEM_PROMPTS_CATALOG_SCHEMA_VERSION:
            raise ValidationError("Unsupported core system prompts schema version.")
        return self


def load_system_prompts_payload_v1() -> SystemPromptsPayloadV1:
    text = (
        resources.files("core.prompts").joinpath("system_prompts.json").read_text(encoding="utf-8")
    )
    try:
        payload = parse_json_value(text)
    except ValidationError as exception:
        raise ValidationError("Failed to parse core system prompts JSON.") from exception
    if not isinstance(payload, dict):
        raise ValidationError("core.prompts.system_prompts must be a JSON object.")
    logger = get_logger(LOGGER_NAME)
    payload, applied_migrations = upgrade_system_prompts_payload_to_current(
        payload,
        logger=logger,
    )
    if applied_migrations:
        logger.warning(
            "System prompts catalog migrations applied: %s",
            list(applied_migrations),
        )
    try:
        return SystemPromptsPayloadV1.model_validate(payload)
    except (pydantic_core.ValidationError, TypeError, ValueError) as exception:
        raise ValidationError("Invalid core system prompts schema.") from exception
