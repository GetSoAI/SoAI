"""SoAI - Core ACL catalog and defaults [backend/core/state/access_policy_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.state.access import AccessAction, AccessState
from core.state.access_policy_catalog_actions import (
    AccessActionCatalogEntry,
    build_access_action_catalog,
)
from core.state.access_policy_catalog_roles import (
    AccessRoleCatalogEntry,
    build_access_role_catalog,
)
from core.state.access_policy_defaults import (
    ADMIN_REQUIRED_ACTIONS,
    IMMUTABLE_POLICY_STATES,
    STANDARD_DEFAULT_ACTIONS,
    STANDARD_GRANTABLE_ACTIONS,
)
from core.types.json import JSONDict

__all__ = (
    "ADMIN_REQUIRED_ACTIONS",
    "IMMUTABLE_POLICY_STATES",
    "STANDARD_DEFAULT_ACTIONS",
    "STANDARD_GRANTABLE_ACTIONS",
    "AccessActionCatalogEntry",
    "AccessRoleCatalogEntry",
    "build_access_policy_catalog",
    "build_access_policy_defaults",
)


def _validate_access_catalog() -> None:
    access_action_catalog = build_access_action_catalog()
    catalog_actions = {entry.action for entry in access_action_catalog}
    enum_actions = set(AccessAction)
    if catalog_actions != enum_actions:
        missing = ", ".join(
            sorted(action.value for action in enum_actions.difference(catalog_actions)),
        )
        extra = ", ".join(
            sorted(action.value for action in catalog_actions.difference(enum_actions)),
        )
        raise StateError(f"ACL action catalog mismatch. Missing: [{missing}] Extra: [{extra}]")
    for entry in access_action_catalog:
        if not entry.locked_roles.issubset(entry.roles):
            raise StateError(
                f"Locked ACL roles must be a subset of visible roles for action '{entry.action.value}'.",
            )


def build_access_policy_catalog() -> JSONDict:
    _validate_access_catalog()
    access_role_catalog = build_access_role_catalog()
    access_action_catalog = build_access_action_catalog()
    return {
        "roles": [
            {
                "id": entry.state.value,
                "mutable": entry.mutable,
                "order": entry.order,
            }
            for entry in access_role_catalog
        ],
        "actions": [
            {
                "id": entry.action.value,
                "roles": [
                    state.value for state in sorted(entry.roles, key=lambda item: item.value)
                ],
                "locked_roles": [
                    state.value for state in sorted(entry.locked_roles, key=lambda item: item.value)
                ],
                "order": entry.order,
            }
            for entry in access_action_catalog
        ],
    }


def build_access_policy_defaults() -> dict[AccessState, frozenset[AccessAction]]:
    return {
        AccessState.UNINITIALIZED: frozenset({AccessAction.WIZARD_BOOTSTRAP}),
        AccessState.ANONYMOUS: frozenset(),
        AccessState.ADMIN: frozenset(AccessAction),
        AccessState.STANDARD: STANDARD_DEFAULT_ACTIONS,
    }
