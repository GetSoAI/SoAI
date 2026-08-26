"""SoAI - Web search schemas [backend/features/api/schemas/web_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr

__all__ = (
    "WebSearchConfig",
    "WebSearchConfigResponse",
    "WebSearchConfigUpdate",
    "WebSearchRequest",
)


class WebSearchConfig(BaseModel):
    enabled: bool = False
    default_provider: str | None = None
    max_results: StrictInt = Field(10, ge=1, le=50)


class WebSearchConfigResponse(WebSearchConfig):
    conv_id: str
    available_providers: list[str] | None = None


class WebSearchConfigUpdate(BaseModel):
    enabled: StrictBool | None = None
    default_provider: StrictStr | None = None
    max_results: StrictInt | None = Field(None, ge=1, le=50)


class WebSearchRequest(BaseModel):
    query: StrictStr = Field(..., min_length=1, max_length=500)
    provider: StrictStr | None = None
    max_results: StrictInt | None = Field(None, ge=1, le=50)
