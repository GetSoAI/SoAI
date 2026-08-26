"""SoAI - OpenAI API context protocols [backend/features/api/runtime/openai_context/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("OpenAIApiContextProtocol",)


class OpenAIApiContextProtocol(Protocol):
    @property
    def dependencies(self) -> ApiDependencies: ...
