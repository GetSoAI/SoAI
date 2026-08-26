"""SoAI - Core ACL policy types and request-state coercion [backend/core/state/access_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from core.errors.exceptions import SecurityError, ValidationError
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.state.access import AccessAction, AccessState

if TYPE_CHECKING:
    from core.state.access import AccessPolicyMatrix
    from core.types.json import JSONValue

__all__ = (
    "AccessPolicyCache",
    "AccessPolicyOverrideError",
    "AccessPolicyUpdate",
    "extract_granted_actions",
    "parse_actions",
)

LOGGER_NAME = "SoAI.core.state.access_policy"


@dataclass(slots=True)
class AccessPolicyCache:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    policy: AccessPolicyMatrix | None = None
    overrides: dict[AccessState, frozenset[AccessAction]] = field(
        default_factory=dict[AccessState, frozenset[AccessAction]],
    )


class AccessPolicyOverrideError(SecurityError): ...


class AccessPolicyUpdate(BaseModel):
    overrides: dict[AccessState, list[AccessAction]] = Field(
        default_factory=dict[AccessState, list[AccessAction]],
    )


def _coerce_access_action_value(value: JSONValue) -> AccessAction:
    if isinstance(value, AccessAction):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValidationError("Access action entries must be non-empty strings.")
        for candidate in (text, text.upper()):
            try:
                return AccessAction(candidate)
            except ValueError:
                member = AccessAction.__members__.get(candidate)
                if isinstance(member, AccessAction):
                    return member
        raise ValidationError(f"Unknown access action '{text}'.")
    raise ValidationError(
        "Access action entries must be provided as AccessAction members or strings.",
    )


def _normalize_granted_actions(
    value: JSONValue | AccessAction | frozenset[AccessAction],
) -> frozenset[AccessAction]:
    if value is None:
        return frozenset()
    if isinstance(value, frozenset) and all(isinstance(entry, AccessAction) for entry in value):
        return value
    if isinstance(value, AccessAction):
        return frozenset({value})
    entries: tuple[JSONValue, ...]
    if isinstance(value, str):
        entries = (value,)
    elif isinstance(value, Mapping):
        entries = tuple(value.keys())
    elif isinstance(value, Sequence):
        if isinstance(value, bytes | bytearray):
            raise ValidationError("Granted actions cannot be provided as byte sequences.")
        entries = tuple(value)
    else:
        raise ValidationError(
            "Granted actions must be provided as iterables or AccessAction members.",
        )
    normalized = tuple(_coerce_access_action_value(entry) for entry in entries)
    return frozenset(normalized)


def extract_granted_actions(request: RequestProtocol) -> frozenset[AccessAction]:
    try:
        current = request.state.granted_actions
    except AttributeError:
        current = None
    normalized = _normalize_granted_actions(current)
    request.state.granted_actions = normalized
    return normalized


def parse_actions(state_value: str, entries: Iterable[JSONValue]) -> frozenset[AccessAction] | None:
    logger = get_logger(LOGGER_NAME)
    actions: set[AccessAction] = set()
    for entry in entries:
        if isinstance(entry, AccessAction):
            actions.add(entry)
            continue
        if isinstance(entry, str):
            value_entry = entry.strip()
            resolved: AccessAction | None = None
            if value_entry:
                try:
                    resolved = AccessAction(value_entry)
                except ValueError:
                    member = AccessAction.__members__.get(value_entry)
                    if isinstance(member, AccessAction):
                        resolved = member
            if resolved is None:
                logger.warning(
                    "Ignoring ACL override for %s due to invalid action '%s'.",
                    state_value,
                    entry,
                )
                return None
            actions.add(resolved)
            continue
        logger.warning(
            "Ignoring ACL override for %s due to invalid action '%s'.",
            state_value,
            entry,
        )
        return None
    return frozenset(actions)
