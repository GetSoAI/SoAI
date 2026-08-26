"""SoAI - Security hardening finding contracts [backend/core/security/hardening_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("SecurityHardeningIssue",)


@dataclass(frozen=True, slots=True)
class SecurityHardeningIssue:
    issue_id: str
    message: str
    config_keys: tuple[str, ...]
    workspace_references: tuple[str, ...] = ()
