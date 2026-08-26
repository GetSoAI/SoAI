"""SoAI - Immutable edition licensing policy [backend/core/licensing/policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.licensing.types import Edition, LicensedProductScope, UseDeclaration

__all__ = ("EditionLicensingPolicy",)


@dataclass(frozen=True, slots=True)
class EditionLicensingPolicy:
    edition: Edition
    legal_catalog_relative_paths: tuple[str, ...]
    legal_document_ids: frozenset[str]
    controlling_license_relative_path: str
    controlling_license_name: str
    evaluation_terms_relative_path: str | None
    evaluation_terms_name: str | None
    personal_purchase_terms_relative_path: str | None
    personal_purchase_terms_name: str | None
    licensed_product_scope: LicensedProductScope
    organizational_evaluation_permitted: bool
    purchase_url: str
    contact_url: str

    def __post_init__(self) -> None:
        if self.edition not in {"soai-core", "soai-os"}:
            raise ValidationError("Licensing edition is invalid.")
        if not self.controlling_license_name.strip():
            raise ValidationError("Controlling license display name is required.")
        if (
            not self.legal_catalog_relative_paths
            or len(set(self.legal_catalog_relative_paths)) != len(self.legal_catalog_relative_paths)
            or not self.legal_document_ids
        ):
            raise ValidationError("Licensing legal catalog policy is invalid.")
        if (self.evaluation_terms_relative_path is None) != (
            self.evaluation_terms_name is None
        ) or (self.personal_purchase_terms_relative_path is None) != (
            self.personal_purchase_terms_name is None
        ):
            raise ValidationError("Licensing document path and display name must be paired.")
        if self.edition == "soai-core":
            if (
                self.licensed_product_scope != "soai_core"
                or not self.organizational_evaluation_permitted
                or self.evaluation_terms_relative_path is None
                or self.personal_purchase_terms_relative_path is not None
            ):
                raise ValidationError("Core licensing policy is contradictory.")
        elif (
            self.licensed_product_scope != "soai_os"
            or self.organizational_evaluation_permitted
            or self.evaluation_terms_relative_path is not None
            or self.personal_purchase_terms_relative_path is None
        ):
            raise ValidationError("SoAI OS licensing policy is contradictory.")
        for relative_path in (
            *self.legal_catalog_relative_paths,
            self.controlling_license_relative_path,
            self.evaluation_terms_relative_path,
            self.personal_purchase_terms_relative_path,
        ):
            if relative_path is not None:
                _validate_relative_path(relative_path)

    def product_access_required(self, declaration: UseDeclaration | None) -> bool:
        return declaration is not None and not (
            self.edition == "soai-core" and declaration == "personal"
        )


def _validate_relative_path(relative_path: str) -> None:
    if (
        not relative_path
        or relative_path.startswith(("/", "\\"))
        or "\\" in relative_path
        or ".." in relative_path.split("/")
    ):
        raise ValidationError("Licensing document path must be a safe relative path.")
