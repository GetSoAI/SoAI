"""SoAI - Sync error deduplication helpers [backend/core/external_accounts/sync_error_dedup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("resolve_previous_sync_error",)


async def resolve_previous_sync_error(
    *,
    prepared_account: JSONDict | None,
    fetch_account: Callable[[], Awaitable[JSONDict | None]],
    logger: LoggerProtocol,
    operation: str,
    sync_label: str,
    details: dict[str, int | str],
) -> str | None:
    account = prepared_account
    if account is None:
        try:
            account = await fetch_account()
        except RECOVERABLE_EXCEPTIONS as exception:
            if sync_label == "calendar":
                log_exception(
                    logger,
                    exception,
                    message=(
                        "Failed to read previous calendar sync error for notification "
                        "de-duplication (non-critical)."
                    ),
                    operation=operation,
                    level="debug",
                    details=details,
                )
            elif sync_label == "mail":
                log_exception(
                    logger,
                    exception,
                    message=(
                        "Failed to read previous mail sync error for notification "
                        "de-duplication (non-critical)."
                    ),
                    operation=operation,
                    level="debug",
                    details=details,
                )
            else:
                raise StateError(
                    f"Unknown sync label: {sync_label!r}.",
                    operation="core.external_accounts.sync_error_dedup.resolve_previous_sync_error",
                ) from exception
            return None
        if account is None:
            return None
    return coerce_optional_trimmed_str(account.get("last_sync_error"))
