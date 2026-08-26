"""SoAI - Ephemeral secret handle store for WebUI vault secret prompts [backend/core/secrets/handle_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import NotRequired, Required, TypedDict

from core.tasks.interaction_secrets import InteractionSecretClaimIdentity
from core.users.user_id import coerce_optional_user_id
from core.validation.strings import coerce_optional_trimmed_str
from core.web.site_scope import SiteScope

__all__ = (
    "SecretHandleStore",
    "SecretPromptPayload",
)


class SecretPromptPayload(TypedDict):
    username: NotRequired[str | None]
    password: Required[str]


@dataclass(frozen=True, slots=True)
class _SecretHandleKey:
    user_id: int
    conv_id: str
    handle: str


@dataclass(frozen=True, slots=True)
class _SecretHandleValue:
    created_at_monotonic: float
    expires_at_monotonic: float
    scope: SiteScope
    payload: SecretPromptPayload
    interaction_secret_identity: InteractionSecretClaimIdentity | None


def _require_store_user_id(user_id: int) -> int:
    normalized_user_id = coerce_optional_user_id(user_id)
    if normalized_user_id is None or normalized_user_id <= 0:
        raise ValueError("user_id must be a positive integer.")
    return normalized_user_id


class SecretHandleStore:
    __slots__ = ("_entries", "_max_entries_per_user", "_max_total_entries")

    def __init__(
        self,
        *,
        max_total_entries: int = 5000,
        max_entries_per_user: int = 200,
    ) -> None:
        resolved_total = int(max_total_entries)
        resolved_per_user = int(max_entries_per_user)
        if resolved_total <= 0:
            raise ValueError("max_total_entries must be positive.")
        if resolved_per_user <= 0:
            raise ValueError("max_entries_per_user must be positive.")
        self._entries: dict[_SecretHandleKey, _SecretHandleValue] = {}
        self._max_total_entries = resolved_total
        self._max_entries_per_user = resolved_per_user

    def create_handle(
        self,
        user_id: int,
        conv_id: str,
        scope: SiteScope,
        payload: SecretPromptPayload,
        *,
        ttl_sec: int = 600,
        interaction_secret_identity: InteractionSecretClaimIdentity | None = None,
    ) -> str:
        normalized_user_id = _require_store_user_id(user_id)
        normalized_conv_id = coerce_optional_trimmed_str(conv_id)
        if not normalized_conv_id:
            raise ValueError("conv_id must not be empty.")
        if int(ttl_sec) <= 0:
            raise ValueError("ttl_sec must be positive.")
        password_value = payload.get("password")
        password_text = password_value if isinstance(password_value, str) else ""
        if password_text == "":
            raise ValueError("payload.password must not be empty.")
        username_value = payload.get("username")
        username_text = username_value if isinstance(username_value, str) else None
        if isinstance(username_text, str) and not username_text.strip():
            username_text = None
        secret_handle = secrets.token_urlsafe(32)
        now = time.monotonic()
        expires_at_monotonic = now + float(ttl_sec)
        key = _SecretHandleKey(
            user_id=normalized_user_id,
            conv_id=normalized_conv_id,
            handle=secret_handle,
        )
        self._entries[key] = _SecretHandleValue(
            created_at_monotonic=now,
            expires_at_monotonic=expires_at_monotonic,
            scope=scope,
            payload={"username": username_text, "password": password_text},
            interaction_secret_identity=interaction_secret_identity,
        )
        self._prune_expired(now_monotonic=now)
        self._enforce_capacity(now_monotonic=now, user_id=normalized_user_id)
        return secret_handle

    def get_handle(
        self,
        user_id: int,
        conv_id: str,
        secret_handle: str,
        *,
        consume: bool = True,
    ) -> SecretPromptPayload | None:
        key = self._coerce_key(user_id=user_id, conv_id=conv_id, secret_handle=secret_handle)
        now = time.monotonic()
        value = self._entries.get(key)
        if value is None:
            self._prune_expired(now_monotonic=now)
            return None
        if now >= value.expires_at_monotonic:
            self._entries.pop(key, None)
            self._prune_expired(now_monotonic=now)
            return None
        if consume:
            self._entries.pop(key, None)
        self._prune_expired(now_monotonic=now)
        payload = value.payload
        username_value = payload.get("username")
        username = username_value if isinstance(username_value, str) else None
        return {"username": username, "password": payload["password"]}

    def get_handle_scope(self, user_id: int, conv_id: str, secret_handle: str) -> SiteScope | None:
        key = self._coerce_key(user_id=user_id, conv_id=conv_id, secret_handle=secret_handle)
        now = time.monotonic()
        value = self._entries.get(key)
        if value is None:
            self._prune_expired(now_monotonic=now)
            return None
        if now >= value.expires_at_monotonic:
            self._entries.pop(key, None)
            self._prune_expired(now_monotonic=now)
            return None
        self._prune_expired(now_monotonic=now)
        return value.scope

    def forget_handle(self, user_id: int, conv_id: str, secret_handle: str) -> None:
        key = self._coerce_key(user_id=user_id, conv_id=conv_id, secret_handle=secret_handle)
        self._entries.pop(key, None)
        self._prune_expired(now_monotonic=time.monotonic())

    def get_interaction_secret_identity(
        self,
        user_id: int,
        conv_id: str,
        secret_handle: str,
    ) -> InteractionSecretClaimIdentity | None:
        key = self._coerce_key(user_id=user_id, conv_id=conv_id, secret_handle=secret_handle)
        now = time.monotonic()
        value = self._entries.get(key)
        if value is None or now >= value.expires_at_monotonic:
            self._entries.pop(key, None)
            self._prune_expired(now_monotonic=now)
            return None
        return value.interaction_secret_identity

    def forget_all_for_interaction_task(self, task_id: str) -> int:
        normalized_task_id = task_id.strip()
        removed_keys = [
            key
            for key, value in self._entries.items()
            if value.interaction_secret_identity is not None
            and value.interaction_secret_identity.task_id == normalized_task_id
        ]
        for key in removed_keys:
            self._entries.pop(key, None)
        self._prune_expired(now_monotonic=time.monotonic())
        return len(removed_keys)

    def forget_all_for_user(self, user_id: int) -> int:
        normalized_user_id = _require_store_user_id(user_id)
        removed_keys: list[_SecretHandleKey] = []
        for key in self._entries:
            if key.user_id == normalized_user_id:
                removed_keys.append(key)
        for key in removed_keys:
            self._entries.pop(key, None)
        self._prune_expired(now_monotonic=time.monotonic())
        return len(removed_keys)

    def _coerce_key(self, *, user_id: int, conv_id: str, secret_handle: str) -> _SecretHandleKey:
        normalized_user_id = _require_store_user_id(user_id)
        normalized_conv_id = coerce_optional_trimmed_str(conv_id)
        normalized_handle = coerce_optional_trimmed_str(secret_handle)
        if not normalized_conv_id:
            raise ValueError("conv_id must not be empty.")
        if not normalized_handle:
            raise ValueError("secret_handle must not be empty.")
        return _SecretHandleKey(
            user_id=normalized_user_id,
            conv_id=normalized_conv_id,
            handle=normalized_handle,
        )

    def _prune_expired(self, *, now_monotonic: float) -> None:
        expired: list[_SecretHandleKey] = []
        for key, value in self._entries.items():
            if now_monotonic >= value.expires_at_monotonic:
                expired.append(key)
        for key in expired:
            self._entries.pop(key, None)

    def _enforce_capacity(self, *, now_monotonic: float, user_id: int) -> None:
        if not self._entries:
            return
        self._prune_expired(now_monotonic=now_monotonic)
        if not self._entries:
            return

        max_total = self._max_total_entries
        max_per_user = self._max_entries_per_user
        if (
            len(self._entries) <= max_total
            and self._count_user_entries(user_id=user_id) <= max_per_user
        ):
            return

        while len(self._entries) > max_total:
            key = self._oldest_key()
            if key is None:
                break
            self._entries.pop(key, None)
        while self._count_user_entries(user_id=user_id) > max_per_user:
            key = self._oldest_key_for_user(user_id=user_id)
            if key is None:
                break
            self._entries.pop(key, None)

    def _count_user_entries(self, *, user_id: int) -> int:
        return sum(1 for key in self._entries if key.user_id == user_id)

    def _oldest_key(self) -> _SecretHandleKey | None:
        oldest_key: _SecretHandleKey | None = None
        oldest_created = 0.0
        for key, value in self._entries.items():
            created = float(value.created_at_monotonic)
            if oldest_key is None or created < oldest_created:
                oldest_key = key
                oldest_created = created
        return oldest_key

    def _oldest_key_for_user(self, *, user_id: int) -> _SecretHandleKey | None:
        oldest_key: _SecretHandleKey | None = None
        oldest_created = 0.0
        for key, value in self._entries.items():
            if key.user_id != user_id:
                continue
            created = float(value.created_at_monotonic)
            if oldest_key is None or created < oldest_created:
                oldest_key = key
                oldest_created = created
        return oldest_key
