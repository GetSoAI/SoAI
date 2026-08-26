"""SoAI - Linked account composition types [backend/core/external_accounts/linked_account_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.external_accounts.protocols import (
    LinkedAccountAuthorizationProtocol,
    LinkedAccountCreationProtocol,
    LinkedAccountMutationProtocol,
    LinkedAccountQueryProtocol,
)

__all__ = ("LinkedAccountCapabilities",)


@dataclass(frozen=True, slots=True)
class LinkedAccountCapabilities:
    creation: LinkedAccountCreationProtocol
    mutations: LinkedAccountMutationProtocol
    queries: LinkedAccountQueryProtocol
    authorization: LinkedAccountAuthorizationProtocol
