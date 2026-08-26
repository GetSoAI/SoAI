"""SoAI - ACL dependency context for middleware [backend/features/api/middleware/acl_dependency_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from fastapi import Request

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("ACLDependencyContext",)


@dataclass(frozen=True, slots=True)
class ACLDependencyContext:
    raise_api_error: Callable[..., NoReturn]
    log_audit_event: Callable[[Request, str, str, Mapping[str, JSONValue] | None], None]
