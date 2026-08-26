"""SoAI - Inference request priority assignment and ordering [backend/core/orchestrator/request_priority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = (
    "DEFAULT_FLEX_PRIORITY_AGING_SECONDS",
    "DEFAULT_STANDARD_PRIORITY_AGING_SECONDS",
    "RequestPriority",
    "RequestPriorityAssignment",
    "RequestSchedulingKey",
    "assign_request_priority",
    "build_default_priority_assignment",
    "validate_priority_aging_windows",
)

DEFAULT_STANDARD_PRIORITY_AGING_SECONDS = 25.0
DEFAULT_FLEX_PRIORITY_AGING_SECONDS = 120.0


class RequestPriority(str, Enum):
    PRIORITY = "priority"
    STANDARD = "standard"
    FLEX = "flex"


@dataclass(frozen=True, slots=True)
class RequestPriorityAssignment:
    priority: RequestPriority
    queued_at: float
    priority_order: float

    def __post_init__(self) -> None:
        if not isinstance(self.priority, RequestPriority):
            raise ValidationError("Request priority assignment has an invalid priority.")
        if isinstance(self.queued_at, bool) or not isinstance(self.queued_at, int | float):
            raise ValidationError("Request priority queue timestamp must be numeric.")
        if not math.isfinite(self.queued_at) or self.queued_at < 0:
            raise ValidationError(
                "Request priority queue timestamp must be finite and non-negative."
            )
        if isinstance(self.priority_order, bool) or not isinstance(
            self.priority_order,
            int | float,
        ):
            raise ValidationError("Request priority order must be numeric.")
        if not math.isfinite(self.priority_order) or self.priority_order < self.queued_at:
            raise ValidationError(
                "Request priority order must be finite and not precede queue time."
            )


@dataclass(frozen=True, order=True, slots=True)
class RequestSchedulingKey:
    priority_order: float
    queued_at: float
    task_id: str


def validate_priority_aging_windows(
    standard_aging_seconds: float,
    flex_aging_seconds: float,
) -> None:
    if not math.isfinite(standard_aging_seconds) or standard_aging_seconds < 0:
        raise ValidationError("Standard priority aging seconds must be finite and non-negative.")
    if not math.isfinite(flex_aging_seconds) or flex_aging_seconds < 0:
        raise ValidationError("Flex priority aging seconds must be finite and non-negative.")
    if flex_aging_seconds < standard_aging_seconds:
        raise ValidationError("Flex priority aging seconds must not be less than standard aging.")


def assign_request_priority(
    payload: JSONDict,
    *,
    queued_at: float,
    standard_aging_seconds: float,
    flex_aging_seconds: float,
) -> RequestPriorityAssignment:
    validate_priority_aging_windows(standard_aging_seconds, flex_aging_seconds)
    service_tier = payload.get("service_tier")
    if service_tier == "priority":
        priority = RequestPriority.PRIORITY
        aging_seconds = 0.0
    elif service_tier == "flex":
        priority = RequestPriority.FLEX
        aging_seconds = flex_aging_seconds
    else:
        priority = RequestPriority.STANDARD
        aging_seconds = standard_aging_seconds
    return RequestPriorityAssignment(
        priority=priority,
        queued_at=queued_at,
        priority_order=queued_at + aging_seconds,
    )


def build_default_priority_assignment() -> RequestPriorityAssignment:
    return assign_request_priority(
        {},
        queued_at=time.time(),
        standard_aging_seconds=DEFAULT_STANDARD_PRIORITY_AGING_SECONDS,
        flex_aging_seconds=DEFAULT_FLEX_PRIORITY_AGING_SECONDS,
    )
