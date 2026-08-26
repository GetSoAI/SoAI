"""SoAI - Linked account domain definition [backend/core/external_accounts/linked_account_definition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("LinkedAccountDefinition",)


@dataclass(frozen=True, slots=True)
class LinkedAccountDefinition:
    account_type: str
    domain_label: str
    owner: str
    external_not_found_message: str
    account_not_found_message: str
    account_not_found_after_update_message: str
