"""SoAI - Core ACL override persistence [backend/core/state/access_policy_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.access import AccessAction, AccessState
from core.state.access_policy import (
    AccessPolicyCache,
    AccessPolicyOverrideError,
    parse_actions,
)
from core.state.access_policy_catalog import (
    ADMIN_REQUIRED_ACTIONS,
    IMMUTABLE_POLICY_STATES,
    STANDARD_GRANTABLE_ACTIONS,
    build_access_policy_catalog,
    build_access_policy_defaults,
)

if TYPE_CHECKING:
    from core.state.access import AccessPolicyMatrix
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_access_policy_response",
    "get_effective_access_policy",
    "load_access_policy_overrides",
    "merge_access_policy",
    "persist_access_policy_overrides",
    "validate_override_entry",
)

LOGGER_NAME = "SoAI.core.state.access_policy_overrides"


def _coerce_access_action_entries(raw: JSONValue) -> tuple[JSONValue, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Iterable):
        return tuple(raw)
    raise ValidationError("Access policy overrides must provide iterables of action identifiers.")


def validate_override_entry(
    state: AccessState,
    actions: frozenset[AccessAction],
) -> frozenset[AccessAction]:
    if state in IMMUTABLE_POLICY_STATES:
        raise AccessPolicyOverrideError(f"State '{state.value}' cannot be overridden.")
    if state is AccessState.ADMIN:
        missing = ADMIN_REQUIRED_ACTIONS.difference(actions)
        if missing:
            required_text = ", ".join(sorted(action.value for action in ADMIN_REQUIRED_ACTIONS))
            raise AccessPolicyOverrideError(f"State '{state.value}' must include: {required_text}.")
    if state is AccessState.STANDARD:
        invalid = actions.difference(STANDARD_GRANTABLE_ACTIONS)
        if invalid:
            allowed_text = ", ".join(
                sorted(action.value for action in STANDARD_GRANTABLE_ACTIONS),
            )
            raise AccessPolicyOverrideError(
                f"State '{state.value}' may only include actions: {allowed_text}.",
            )
    return actions


def merge_access_policy(
    overrides: dict[AccessState, frozenset[AccessAction]] | None = None,
) -> AccessPolicyMatrix:
    merged = dict(build_access_policy_defaults())
    if overrides:
        merged.update(overrides)
    return merged


def _set_access_policy_cache(
    cache: AccessPolicyCache,
    policy: AccessPolicyMatrix,
    overrides: dict[AccessState, frozenset[AccessAction]],
) -> None:
    cache.policy = policy
    cache.overrides = dict(overrides)


def _format_state_action_view(
    entries: Iterable[tuple[AccessState, frozenset[AccessAction]]],
) -> dict[str, list[str]]:
    view: dict[str, list[str]] = {}
    for state, actions in entries:
        view[state.value] = sorted(action.value for action in actions)
    return view


def _policy_matrix_to_dict(
    matrix: Mapping[AccessState, frozenset[AccessAction]],
) -> dict[str, list[str]]:
    pairs = ((state, matrix.get(state, frozenset())) for state in AccessState)
    return _format_state_action_view(pairs)


def _get_sort_key_for_state_tuple(item: tuple[AccessState, frozenset[AccessAction]]) -> str:
    return item[0].value


def _overrides_to_dict(
    overrides: dict[AccessState, frozenset[AccessAction]],
) -> dict[str, list[str]]:
    return _format_state_action_view(sorted(overrides.items(), key=_get_sort_key_for_state_tuple))


def _serialize_access_policy_overrides(
    overrides: dict[AccessState, frozenset[AccessAction]] | None,
) -> dict[str, list[str]] | None:
    if not overrides:
        return None
    return _overrides_to_dict(overrides)


async def load_access_policy_overrides(
    database_plugins: DatabasePluginsProtocol,
) -> dict[AccessState, frozenset[AccessAction]]:
    logger = get_logger(LOGGER_NAME)
    stored = await database_plugins.get_system_setting("access_policy_overrides")
    if stored is None:
        return {}
    if not isinstance(stored, dict):
        logger.warning("Access policy overrides must be stored as a mapping.")
        return {}
    normalized: dict[AccessState, frozenset[AccessAction]] = {}
    for state_name, entries in stored.items():
        try:
            state = AccessState(state_name)
        except ValueError:
            logger.warning("Ignoring ACL override for unknown state '%s'.", state_name)
            continue
        try:
            values = _coerce_access_action_entries(entries)
        except ValidationError as exception:
            logger.warning(
                "Ignoring ACL override for %s due to invalid entries: %s",
                state.value,
                str(exception),
            )
            continue
        candidate = parse_actions(state.value, values)
        if candidate is None:
            continue
        try:
            normalized[state] = validate_override_entry(state, candidate)
        except AccessPolicyOverrideError as exception:
            logger.warning(
                "Ignoring invalid ACL override for %s: %s",
                state.value,
                str(exception),
            )
    return normalized


async def get_effective_access_policy(
    cache: AccessPolicyCache,
    database_plugins: DatabasePluginsProtocol,
) -> AccessPolicyMatrix:
    async with cache.lock:
        if cache.policy is not None:
            return cache.policy
        overrides = await load_access_policy_overrides(database_plugins)
        policy = merge_access_policy(overrides)
        _set_access_policy_cache(cache, policy, overrides)
        return policy


async def persist_access_policy_overrides(
    cache: AccessPolicyCache,
    overrides: dict[AccessState, frozenset[AccessAction]] | None,
    database_plugins: DatabasePluginsProtocol,
) -> AccessPolicyMatrix:
    serialized = _serialize_access_policy_overrides(overrides)
    effective_overrides = overrides or {}
    policy = merge_access_policy(effective_overrides)
    async with cache.lock:
        await database_plugins.set_system_setting("access_policy_overrides", serialized)
        _set_access_policy_cache(cache, policy, effective_overrides)
    return policy


def build_access_policy_response(
    policy: AccessPolicyMatrix,
    overrides: dict[AccessState, frozenset[AccessAction]],
) -> JSONDict:
    return {
        "effective": _policy_matrix_to_dict(policy),
        "defaults": _policy_matrix_to_dict(build_access_policy_defaults()),
        "overrides": _overrides_to_dict(overrides),
        "catalog": build_access_policy_catalog(),
    }
