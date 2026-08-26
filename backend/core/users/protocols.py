"""SoAI - Core user protocols [backend/core/users/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ("UserIdCarrierProtocol",)


@runtime_checkable
class UserIdCarrierProtocol(Protocol):
    user_id: int | bool | None
