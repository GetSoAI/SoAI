"""SoAI - OpenAI API key assignment outcomes [backend/core/auth/api_key_assignment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import StrEnum

__all__ = ("APIKeyAssignmentOutcome",)


class APIKeyAssignmentOutcome(StrEnum):
    ASSIGNED = "assigned"
    API_KEY_NOT_FOUND = "api_key_not_found"
    API_KEY_INACTIVE = "api_key_inactive"
    USER_NOT_FOUND = "user_not_found"
