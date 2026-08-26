"""SoAI - Tool approval interaction schemas [backend/features/api/schemas/tool_approval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = ("ToolApprovalResolveRequest",)


class ToolApprovalResolveRequest(SoAIV1StrictModel):
    action: Literal["approve", "deny", "cancel"]
    remember: bool = False

    @model_validator(mode="after")
    def validate_remember_scope(self) -> ToolApprovalResolveRequest:
        if self.remember and self.action != "approve":
            raise ValidationError("remember can only be true when action is approve")
        return self
