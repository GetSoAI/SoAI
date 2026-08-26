"""SoAI - Strict local licensing API schemas [backend/features/api/schemas/licensing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.licensing.declaration import PERSONAL_USE_ATTESTATION_REVISION
from core.licensing.timestamps import parse_licensing_timestamp
from core.licensing.types import LicensingActivationInput
from core.types.json import JSONValue
from core.users.username import require_canonical_username
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from core.validation.password_strength import PasswordStrengthEvaluator


class WizardLicensingMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    draft_revision: int = Field(strict=True, ge=0, le=JAVASCRIPT_SAFE_INTEGER_MAX)


class WizardLicenseAcceptance(WizardLicensingMutation):
    fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class WizardUseDeclaration(WizardLicensingMutation):
    declaration: Literal["personal", "organization_commercial"]
    attestation_confirmed: bool
    attestation_revision: str | None

    @model_validator(mode="after")
    def validate_attestation(self) -> "WizardUseDeclaration":
        if self.declaration == "personal":
            if (
                self.attestation_confirmed is not True
                or self.attestation_revision != PERSONAL_USE_ATTESTATION_REVISION
            ):
                raise ValidationError("Current personal-use attestation is required.")
        elif self.attestation_confirmed is not False or self.attestation_revision is not None:
            raise ValidationError("Organizational use cannot carry a personal attestation.")
        return self


class WizardEvaluationRequest(WizardLicensingMutation):
    organization: "LicensingOrganization"
    legal_acceptances: tuple["LicensingLegalAcceptance", ...]

    @field_validator("legal_acceptances")
    @classmethod
    def validate_acceptances(
        cls, value: tuple["LicensingLegalAcceptance", ...]
    ) -> tuple["LicensingLegalAcceptance", ...]:
        return _require_sorted_acceptances(value)


class WizardActivationRequest(WizardLicensingMutation):
    activation_source: Literal["evaluation", "credential"]
    pending_evaluation_id: str | None = Field(default=None, min_length=16, max_length=128)
    activation_credential: str | None = Field(
        default=None, min_length=16, max_length=192, repr=False
    )
    deployment_environment: Literal["production", "non_production"] | None = None
    legal_acceptances: tuple["LicensingLegalAcceptance", ...]

    @field_validator("legal_acceptances")
    @classmethod
    def validate_acceptances(
        cls, value: tuple["LicensingLegalAcceptance", ...]
    ) -> tuple["LicensingLegalAcceptance", ...]:
        return _require_sorted_acceptances(value)

    @model_validator(mode="after")
    def validate_source(self) -> "WizardActivationRequest":
        if self.activation_source == "evaluation":
            if self.pending_evaluation_id is None or self.activation_credential is not None:
                raise ValidationError("Evaluation activation input is contradictory.")
            if self.deployment_environment is not None:
                raise ValidationError("Evaluation activation has no environment.")
        elif self.activation_credential is None or self.pending_evaluation_id is not None:
            raise ValidationError("Credential activation input is contradictory.")
        return self

    def to_licensing_input(self, now_ms: int) -> LicensingActivationInput:
        return LicensingActivationInput(
            draft_revision=self.draft_revision,
            activation_source=self.activation_source,
            pending_evaluation_id=self.pending_evaluation_id,
            activation_credential=self.activation_credential,
            deployment_environment=self.deployment_environment,
            legal_acceptances=[value.model_dump(mode="json") for value in self.legal_acceptances],
            now_ms=now_ms,
        )


class LicensingLegalAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    document_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    version: str = Field(pattern=r"^[1-9][0-9]*\.[0-9]+$")
    accepted_at: datetime

    @field_validator("accepted_at", mode="before")
    @classmethod
    def validate_accepted_at(cls, value: JSONValue) -> datetime:
        return parse_licensing_timestamp(value, field="accepted_at")


class LicensingOrganization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    legal_name: str = Field(min_length=1, max_length=256)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    registration_or_tax_id: str = Field(min_length=1, max_length=256)
    authorized_acceptor_name: str = Field(min_length=1, max_length=256)
    authorized_acceptor_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    authority_attested: Literal[True]

    @field_validator("legal_name", "registration_or_tax_id", "authorized_acceptor_name")
    @classmethod
    def validate_display_value(cls, value: str) -> str:
        if value.strip() != value or any(ord(character) < 32 for character in value):
            raise ValidationError("Organization display value is invalid.")
        return value


def _require_sorted_acceptances(
    value: tuple[LicensingLegalAcceptance, ...],
) -> tuple[LicensingLegalAcceptance, ...]:
    identities = tuple(acceptance.document_id for acceptance in value)
    if not identities or identities != tuple(sorted(set(identities))):
        raise ValidationError("Legal acceptances must be sorted and unique.")
    return value


class LicensingDeactivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    reason: Literal["rehost", "retired", "disaster_recovery", "other"]


class LicensingOfflineRequest(WizardLicensingMutation):
    deployment_environment: Literal["production", "non_production"] | None = None
    license_reference: str | None = Field(default=None, min_length=1, max_length=128)


class LicensingOsEvaluationConversion(WizardLicensingMutation):
    organization: LicensingOrganization
    legal_acceptances: tuple[LicensingLegalAcceptance, ...]

    @field_validator("legal_acceptances")
    @classmethod
    def validate_acceptances(
        cls, value: tuple[LicensingLegalAcceptance, ...]
    ) -> tuple[LicensingLegalAcceptance, ...]:
        return _require_sorted_acceptances(value)


class LicensingOsEvaluationReversion(WizardLicensingMutation):
    company_use_ended: Literal[True]
    company_data_handled: Literal[True]


class LicensingCommercialConversion(WizardLicensingMutation):
    activation_credential: str = Field(min_length=16, max_length=192, repr=False)
    deployment_environment: Literal["production", "non_production"]
    legal_acceptances: tuple[LicensingLegalAcceptance, ...]

    @field_validator("legal_acceptances")
    @classmethod
    def validate_acceptances(
        cls, value: tuple[LicensingLegalAcceptance, ...]
    ) -> tuple[LicensingLegalAcceptance, ...]:
        return _require_sorted_acceptances(value)


class LicensingDeploymentReclassification(WizardLicensingMutation):
    deployment_environment: Literal["production", "non_production"]


class WizardCompletionRequest(WizardLicensingMutation):
    username: str = Field(min_length=1, max_length=128)
    language: Literal[
        "af",
        "ar",
        "de",
        "en",
        "es",
        "fa",
        "fr",
        "hi",
        "id",
        "it",
        "ja",
        "ko",
        "nl",
        "pl",
        "pt",
        "ru",
        "th",
        "tr",
        "uk",
        "vi",
        "zh",
        "zh-Hant",
    ]
    password: str = Field(
        min_length=PasswordStrengthEvaluator.MIN_LENGTH,
        max_length=PasswordStrengthEvaluator.MAX_LENGTH,
        repr=False,
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return require_canonical_username(value)


__all__ = (
    "WizardActivationRequest",
    "LicensingDeactivationRequest",
    "LicensingOfflineRequest",
    "LicensingCommercialConversion",
    "LicensingDeploymentReclassification",
    "LicensingOsEvaluationConversion",
    "LicensingOsEvaluationReversion",
    "WizardCompletionRequest",
    "WizardEvaluationRequest",
    "WizardLicenseAcceptance",
    "LicensingLegalAcceptance",
    "LicensingOrganization",
    "WizardLicensingMutation",
    "WizardUseDeclaration",
)
