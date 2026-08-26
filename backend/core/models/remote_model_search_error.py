"""SoAI - Remote model search error type [backend/core/models/remote_model_search_error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.external_service_exception import ExternalServiceError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("RemoteModelSearchError",)


class RemoteModelSearchError(ExternalServiceError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, details={"status_code": status_code, "retryable": retryable})
        self.status_code = status_code
        self.retryable = retryable

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.message,), {"status_code": self.status_code, "retryable": self.retryable})
