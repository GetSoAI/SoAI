"""SoAI - OpenAI image request/response schemas [backend/features/api/schemas/openai_images.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.openai.image_model_validation import (
    validate_image_edit_json_model,
    validate_image_generation_model_fields,
)
from core.timing.epoch import epoch_seconds

__all__ = (
    "ImageEditJsonRequest",
    "ImageGenerationRequest",
    "ImageGenerationResponse",
    "ImageRefParam",
)


class ImageGenerationRequest(SoAIV1StrictModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="A text description of the desired image(s).",
    )
    model: str | None = Field(
        None,
        min_length=1,
        description=(
            "The model to use. Optional per the OpenAI spec; when omitted SoAI will apply "
            "the OpenAI-documented default model selection logic."
        ),
    )
    completion_count: StrictInt | None = Field(
        1,
        ge=1,
        le=10,
        description="The number of images to generate.",
        alias="n",
    )
    size: str | None = Field(None, description="Requested image size.")
    quality: str | None = Field(None, description="Requested rendering quality.")
    moderation: Literal["low", "auto"] | None = Field(
        None,
        description="Moderation level for GPT image models.",
    )
    background: str | None = Field(
        None,
        description="Requested background, e.g. transparent/opaque.",
    )
    output_format: str | None = Field(
        None,
        description="Requested output file format, e.g. png/jpeg/webp.",
    )
    output_compression: StrictInt | None = Field(
        None,
        ge=0,
        le=100,
        description="Compression level (0-100) for jpeg/webp outputs.",
    )
    response_format: Literal["url", "b64_json"] | None = Field(
        None,
        description="Response format selector for DALL·E-style providers.",
    )
    style: Literal["vivid", "natural"] | None = Field(None, description="DALL·E 3 style selector.")
    user: str | None = None
    stream: StrictBool | None = None
    partial_images: StrictInt | None = Field(None, ge=0, le=3)

    @model_validator(mode="after")
    def validate_image_request(self) -> ImageGenerationRequest:
        validate_image_generation_model_fields(
            self.model or "",
            has_response_format=self.response_format is not None,
            has_style=self.style is not None,
            has_background=self.background is not None,
            has_output_format=self.output_format is not None,
            has_output_compression=self.output_compression is not None,
        )
        return self


class ImageData(BaseModel):
    b64_json: str | None = None
    url: AnyHttpUrl | None = None
    revised_prompt: str | None = Field(
        None,
        description="The revised prompt that was used to generate the image, if applicable.",
    )


class ImageGenerationResponse(BaseModel):
    created: int = Field(default_factory=lambda: int(epoch_seconds()))
    data: list[ImageData]


class ImageRefParam(SoAIV1StrictModel):
    image_url: str | None = None
    file_id: str | None = None

    @model_validator(mode="after")
    def validate_ref(self) -> ImageRefParam:
        has_url = isinstance(self.image_url, str) and bool(self.image_url.strip())
        has_file = isinstance(self.file_id, str) and bool(self.file_id.strip())
        if has_url == has_file:
            raise ValidationError("Provide exactly one of image_url or file_id.")
        return self


class ImageEditJsonRequest(SoAIV1StrictModel):
    model: str = Field(..., min_length=1)
    images: list[ImageRefParam] = Field(..., min_length=1, max_length=16)
    mask: ImageRefParam | None = None
    prompt: str = Field(..., min_length=1, max_length=32000)
    completion_count: StrictInt | None = Field(1, ge=1, le=10, alias="n")
    quality: Literal["low", "medium", "high", "auto"] | None = "auto"
    input_fidelity: Literal["high", "low"] | None = None
    size: Literal["auto", "1024x1024", "1536x1024", "1024x1536"] | None = "auto"
    user: str | None = None
    output_format: Literal["png", "jpeg", "webp"] | None = "png"
    output_compression: StrictInt | None = Field(None, ge=0, le=100)
    moderation: Literal["low", "auto"] | None = "auto"
    background: Literal["transparent", "opaque", "auto"] | None = "auto"
    stream: StrictBool | None = False
    partial_images: StrictInt | None = Field(None, ge=0, le=3)

    @model_validator(mode="after")
    def reject_dalle_models(self) -> ImageEditJsonRequest:
        validate_image_edit_json_model(self.model or "")
        return self
