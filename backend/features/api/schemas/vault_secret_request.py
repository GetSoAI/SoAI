"""SoAI - Vault secret prompt interaction schemas [backend/features/api/schemas/vault_secret_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = ("VaultSecretRequestResolveRequest",)


class VaultSecretRequestResolveRequest(SoAIV1StrictModel):
    action: Literal["submit", "cancel"]
    username: str | None = None
    password: str | None = None
    save_to_vault: bool = False
    label: str | None = None

    @model_validator(mode="after")
    def validate_submit_requirements(self) -> VaultSecretRequestResolveRequest:
        if self.action == "submit":
            password_value = self.password if isinstance(self.password, str) else None
            if password_value is None or password_value == "":
                raise ValidationError("password is required")
            if self.save_to_vault:
                label_value = self.label.strip() if isinstance(self.label, str) else ""
                if not label_value:
                    raise ValidationError("label is required when save_to_vault is true")
        return self
