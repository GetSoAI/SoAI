"""SoAI - WebUI tool icon catalog response schemas [backend/features/api/schemas/webui_tool_icons.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ("WebuiToolIcon", "WebuiToolIconCatalogResponse")


class WebuiToolIcon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    src: str


class WebuiToolIconCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icons: list[WebuiToolIcon]
