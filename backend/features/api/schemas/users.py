"""SoAI - User and login API schemas [backend/features/api/schemas/users.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.users.username import require_canonical_username
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from core.validation.password_strength import PasswordStrengthEvaluator
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "AdminUserCreate",
    "AdminUserRoleUpdate",
    "AdminUserWorkspacePathUpdate",
    "AdminWorkspaceBrowserLocate",
    "LoginPayload",
    "SessionRotationRecoveryPayload",
    "WEBUI_PASSWORD_MIN_LENGTH",
    "WEBUI_PASSWORD_MAX_LENGTH",
    "UserBase",
    "UserCreate",
    "UserPasswordUpdate",
    "UsernameRenamePayload",
    "UserMutationStatusPayload",
    "UserPreferencesUpdate",
    "WebuiAndroidSessionRename",
)

WEBUI_PASSWORD_MIN_LENGTH = PasswordStrengthEvaluator.MIN_LENGTH
WEBUI_PASSWORD_MAX_LENGTH = PasswordStrengthEvaluator.MAX_LENGTH


class UserBase(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return require_canonical_username(value)


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=WEBUI_PASSWORD_MIN_LENGTH,
        max_length=WEBUI_PASSWORD_MAX_LENGTH,
    )
    is_admin: bool = False


class AdminUserCreate(UserCreate): ...


class UserPasswordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str
    current_password: str = Field(..., min_length=1, max_length=WEBUI_PASSWORD_MAX_LENGTH)
    new_password: str = Field(
        ...,
        min_length=WEBUI_PASSWORD_MIN_LENGTH,
        max_length=WEBUI_PASSWORD_MAX_LENGTH,
    )

    @field_validator("operation_id")
    @classmethod
    def validate_operation_id(cls, value: str) -> str:
        return require_mutation_request_id(value)


class UsernameRenamePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str
    new_username: str
    current_password: str = Field(..., min_length=1, max_length=WEBUI_PASSWORD_MAX_LENGTH)

    @field_validator("operation_id")
    @classmethod
    def validate_operation_id(cls, value: str) -> str:
        return require_mutation_request_id(value)

    @field_validator("new_username")
    @classmethod
    def validate_new_username(cls, value: str) -> str:
        return require_canonical_username(value)


class SessionRotationRecoveryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str | None = None

    @field_validator("operation_id")
    @classmethod
    def validate_operation_id(cls, value: str | None) -> str | None:
        return require_mutation_request_id(value) if value is not None else None

    @model_validator(mode="after")
    def reject_explicit_null_operation_id(self) -> "SessionRotationRecoveryPayload":
        if "operation_id" in self.model_fields_set and self.operation_id is None:
            raise ValidationError("operation_id cannot be null.")
        return self


class UserMutationStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finalize_absence: bool | None = None
    operation_type: Literal["username_rename", "password_change"] | None = None
    target_user_id: int | None = Field(
        default=None,
        strict=True,
        gt=0,
        le=JAVASCRIPT_SAFE_INTEGER_MAX,
    )
    requested_username: str | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> "UserMutationStatusPayload":
        values = (
            self.finalize_absence,
            self.operation_type,
            self.target_user_id,
            self.requested_username,
        )
        if all(value is None for value in values):
            return self
        if self.finalize_absence is not True:
            raise ValidationError("finalize_absence must be true when supplied.")
        if self.operation_type is None:
            raise ValidationError("operation_type is invalid.")
        if self.target_user_id is None:
            raise ValidationError("target_user_id is required.")
        if self.operation_type == "username_rename":
            if self.requested_username is None:
                raise ValidationError("requested_username is required for rename.")
            self.requested_username = require_canonical_username(self.requested_username)
        elif self.requested_username is not None:
            raise ValidationError("requested_username is invalid for password change.")
        return self


class AdminUserRoleUpdate(BaseModel):
    is_admin: bool


class AdminUserWorkspacePathUpdate(BaseModel):
    workspace_path: str | None = None


class AdminWorkspaceBrowserLocate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str


class UserPreferencesUpdate(BaseModel):
    preferences: dict[str, PydanticJSONValue]
    intended_user_id: int | None = Field(
        default=None, strict=True, gt=0, le=JAVASCRIPT_SAFE_INTEGER_MAX
    )


class WebuiAndroidSessionRename(BaseModel):
    device_id: str = Field(..., min_length=36, max_length=36)
    device_label: str = Field(..., min_length=1, max_length=80)


class LoginPayload(UserBase):
    password: str = Field(..., min_length=1, max_length=WEBUI_PASSWORD_MAX_LENGTH)
