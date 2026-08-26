"""SoAI - Password vault label normalization helpers [backend/database/repositories/users/password_vault_label_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "normalize_password_vault_label",
    "normalize_password_vault_label_lookup",
    "normalize_password_vault_search_query",
)


def normalize_password_vault_label(label: str) -> str:
    normalized_label = label.strip()
    if not normalized_label:
        raise ValidationError("Password vault label must not be empty.")
    return normalized_label


def normalize_password_vault_label_lookup(label: str) -> str:
    return normalize_password_vault_label(label).lower()


def normalize_password_vault_search_query(query: str | None) -> str | None:
    if not isinstance(query, str):
        return None
    normalized_query = query.strip().lower()
    if not normalized_query:
        return None
    return normalized_query
