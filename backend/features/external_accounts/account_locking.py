"""SoAI - Shared account lock normalization [backend/features/external_accounts/account_locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.protocols import (
    AsyncContextManagerProtocol,
    AsyncLockRegistryProtocol,
)
from core.errors.exceptions import ValidationError
from features.external_accounts.internal_protocols import AccountLockAcquirer

__all__ = (
    "AccountLockAcquirer",
    "acquire_account_lock",
    "bind_account_lock",
    "require_account_lock_id",
)


def require_account_lock_id(account_id: str, *, label: str) -> str:
    normalized_account_id = str(account_id or "").strip()
    if not normalized_account_id:
        raise ValidationError(f"{label} is invalid.")
    return normalized_account_id


def acquire_account_lock(
    lock_registry: AsyncLockRegistryProtocol[tuple[int, str]],
    *,
    user_id: int,
    account_id: str,
    label: str,
) -> AsyncContextManagerProtocol[None]:
    return lock_registry.lock((int(user_id), require_account_lock_id(account_id, label=label)))


def bind_account_lock(
    lock_registry: AsyncLockRegistryProtocol[tuple[int, str]],
    *,
    label: str,
) -> AccountLockAcquirer:
    return partial(acquire_account_lock, lock_registry, label=label)
