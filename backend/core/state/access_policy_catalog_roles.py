"""SoAI - Core ACL role catalog entries [backend/core/state/access_policy_catalog_roles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.state.access import AccessState

__all__ = (
    "AccessRoleCatalogEntry",
    "build_access_role_catalog",
)


@dataclass(frozen=True, slots=True)
class AccessRoleCatalogEntry:
    state: AccessState
    mutable: bool
    order: int


def build_access_role_catalog() -> tuple[AccessRoleCatalogEntry, ...]:
    return (
        AccessRoleCatalogEntry(
            state=AccessState.UNINITIALIZED,
            mutable=False,
            order=10,
        ),
        AccessRoleCatalogEntry(
            state=AccessState.ANONYMOUS,
            mutable=False,
            order=15,
        ),
        AccessRoleCatalogEntry(
            state=AccessState.ADMIN,
            mutable=True,
            order=20,
        ),
        AccessRoleCatalogEntry(
            state=AccessState.STANDARD,
            mutable=True,
            order=30,
        ),
    )
