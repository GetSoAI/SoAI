"""SoAI - Native SoAI V1 schema bases [backend/core/meta/soai_v1.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = (
    "SoAIV1ExtensibleModel",
    "SoAIV1StrictModel",
)


class SoAIV1StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SoAIV1ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")
