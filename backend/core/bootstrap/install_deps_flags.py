"""SoAI - Install dependency CLI flags [backend/core/bootstrap/install_deps_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

__all__ = (
    "INSTALL_DEPS_BARE_COMMAND",
    "INSTALL_DEPS_FLAG_VARIANTS",
    "INSTALL_DEPS_LONG_OPTION",
    "INSTALL_DEPS_SHORT_OPTION",
    "contains_install_deps_flag",
)

INSTALL_DEPS_BARE_COMMAND = "install-deps"
INSTALL_DEPS_SHORT_OPTION = "-install-deps"
INSTALL_DEPS_LONG_OPTION = "--install-deps"
INSTALL_DEPS_FLAG_VARIANTS: frozenset[str] = frozenset(
    {
        INSTALL_DEPS_BARE_COMMAND,
        INSTALL_DEPS_SHORT_OPTION,
        INSTALL_DEPS_LONG_OPTION,
    },
)


def contains_install_deps_flag(argv: Sequence[str]) -> bool:
    for arg in argv:
        if arg in INSTALL_DEPS_FLAG_VARIANTS:
            return True
    return False
