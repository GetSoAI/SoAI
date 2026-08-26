"""SoAI - Automation route query validation [backend/features/api/routes/automations/query_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.automation.automation_constants import (
    AUTOMATION_OCCURRENCES_MAX_ITEMS,
    AUTOMATION_RUNS_MAX_LIMIT,
)
from core.errors.exceptions import ValidationError
from features.api.runtime.errors import raise_bad_request
from features.automation.occurrence_window_bounds import validate_window_range

__all__ = (
    "require_automation_list_pagination",
    "require_automation_occurrences_pagination",
    "require_automation_runs_pagination",
    "require_automation_window_bounds",
)


def require_automation_list_pagination(
    request: Request,
    *,
    limit: int,
    offset: int,
    max_limit: int,
) -> None:
    if limit < 1 or limit > max_limit:
        raise_bad_request(
            request,
            f"Automation list limit cannot exceed {max_limit}.",
        )
    if offset < 0:
        raise_bad_request(
            request,
            "Automation list offset must be zero or greater.",
        )


def require_automation_window_bounds(request: Request, *, from_utc_ms: int, to_utc_ms: int) -> None:
    try:
        validate_window_range(from_utc_ms, to_utc_ms)
    except ValidationError as exception:
        raise_bad_request(
            request,
            str(exception),
        )


def require_automation_runs_pagination(request: Request, *, limit: int, offset: int) -> None:
    if limit < 1 or limit > AUTOMATION_RUNS_MAX_LIMIT:
        raise_bad_request(
            request,
            f"Automation runs limit cannot exceed {AUTOMATION_RUNS_MAX_LIMIT}.",
        )
    if offset < 0:
        raise_bad_request(
            request,
            "Automation runs offset must be zero or greater.",
        )


def require_automation_occurrences_pagination(request: Request, *, limit: int, offset: int) -> None:
    if limit < 1 or limit > AUTOMATION_OCCURRENCES_MAX_ITEMS:
        raise_bad_request(
            request,
            f"Automation occurrences limit cannot exceed {AUTOMATION_OCCURRENCES_MAX_ITEMS}.",
        )
    if offset < 0:
        raise_bad_request(
            request,
            "Automation occurrences offset must be zero or greater.",
        )
