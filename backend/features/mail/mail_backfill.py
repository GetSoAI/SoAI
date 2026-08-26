"""SoAI - Mail folder backfill methods [backend/features/mail/mail_backfill.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.mail.imap_reads import run_imap_backfill_batch_sync
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_imports import import_folder_messages
from features.mail.pop3_reads import run_pop3_backfill_batch_reverse_sync
from features.mail.runtime_state import load_mail_folder_runtime
from features.mail.transport_context import prepare_mail_transport_context

__all__ = ("backfill_folder_method",)


async def backfill_folder_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    folder_id: str,
    arguments: JSONDict,
) -> JSONDict:
    if self.runtime_flags.offline_mode:
        raise ValidationError("Mail backfill is unavailable while offline mode is enabled.")
    runtime_state, folder_runtime = await load_mail_folder_runtime(
        database_mail=self.database_mail,
        external_accounts=self.external_accounts,
        user_id=user_id,
        folder_id=folder_id,
        decrypt_secrets=True,
    )
    async with self.account_lock(user_id=user_id, account_id=runtime_state.account_id):
        runtime_state, folder_runtime = await load_mail_folder_runtime(
            database_mail=self.database_mail,
            external_accounts=self.external_accounts,
            user_id=user_id,
            folder_id=folder_id,
            decrypt_secrets=True,
        )
        batch_limit = coerce_positive_int(
            arguments.get("batch_limit"),
            default=int(self.config.get_int("INTEGRATIONS.MAIL.BACKFILL.BATCH_LIMIT_DEFAULT")),
            minimum=1,
            maximum=int(self.config.get_int("INTEGRATIONS.MAIL.BACKFILL.BATCH_LIMIT_MAX")),
        )
        before_ms = coerce_optional_non_negative_int_strict(arguments.get("before_ms"))
        prepared = await prepare_mail_transport_context(
            config=self.config,
            runtime_flags=self.runtime_flags,
            database_mail=self.database_mail,
            external_accounts=self.external_accounts,
            user_id=user_id,
            account_id=runtime_state.account_id,
        )
        checkpoint = await _read_backfill_checkpoint(self, user_id=user_id, folder_id=folder_id)
        existing_messages = await self.database_mail.list_messages(
            user_id=user_id,
            folder_id=folder_id,
        )
        if prepared.runtime_state.protocol == "imap":
            anchor_uid = _oldest_cached_uid(existing_messages)
            batch = await run_bounded_blocking_call(
                self.mail_blocking_pool,
                partial(
                    run_imap_backfill_batch_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    remote_mailbox=folder_runtime.remote_mailbox,
                    batch_limit=batch_limit,
                    end_index_exclusive=_read_checkpoint_end_index(checkpoint, before_ms=before_ms),
                    anchor_uid=anchor_uid,
                    before_ms=before_ms,
                    snippet_max_chars=int(
                        self.config.get_int("INTEGRATIONS.MAIL.LIMITS.SNIPPET_MAX_CHARS"),
                    ),
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            checkpoint_payload = {
                "before_ms": before_ms,
                "next_end_index": _read_batch_count(batch, "next_end_index"),
                "uidvalidity": (
                    batch.get("uidvalidity") if isinstance(batch.get("uidvalidity"), int) else None
                ),
            }
        else:
            anchor_uidl = _oldest_cached_uidl(existing_messages)
            batch = await run_bounded_blocking_call(
                self.mail_blocking_pool,
                partial(
                    run_pop3_backfill_batch_reverse_sync,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    batch_limit=batch_limit,
                    end_index_exclusive=_read_checkpoint_end_index(checkpoint, before_ms=before_ms),
                    anchor_uidl=anchor_uidl,
                    snippet_max_chars=int(
                        self.config.get_int("INTEGRATIONS.MAIL.LIMITS.SNIPPET_MAX_CHARS"),
                    ),
                ),
                timeout_sec=prepared.connect_timeout_sec
                + float(self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
            )
            checkpoint_payload = {
                "before_ms": before_ms,
                "next_end_index": _read_batch_count(batch, "next_end_index"),
            }
        message_payloads_value = batch.get("messages")
        message_payloads: list[JSONDict] = []
        if isinstance(message_payloads_value, list):
            for item in message_payloads_value:
                if isinstance(item, dict):
                    message_payloads.append(item)
        import_result = await import_folder_messages(
            database_mail=self.database_mail,
            user_id=user_id,
            account_id=runtime_state.account_id,
            folder_payload=folder_runtime.folder,
            message_payloads=message_payloads,
        )
        await self.database_mail.update_backfill_state(
            user_id=user_id,
            folder_id=folder_id,
            checkpoint_json=serialize_json_compact_stable_strict(checkpoint_payload),
            last_backfill_at_ms=epoch_ms(),
        )
        all_messages = await self.database_mail.list_messages(user_id=user_id, folder_id=folder_id)
        updated_count = _read_batch_count(import_result, "updated_count")
        imported_count = _read_batch_count(import_result, "imported_count")
        skipped_count = max(len(message_payloads) - imported_count - updated_count, 0)
        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "oldest_cached_received_at_ms": _oldest_cached_received_at_ms(all_messages),
            "has_more": batch.get("has_more") is True,
        }


async def _read_backfill_checkpoint(
    service: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    folder_id: str,
) -> JSONDict | None:
    state = await service.database_mail.get_backfill_state(user_id=user_id, folder_id=folder_id)
    if state is None:
        return None
    checkpoint_json_value = state.get("checkpoint_json")
    if not isinstance(checkpoint_json_value, str) or not checkpoint_json_value.strip():
        return None
    parsed = parse_json_value(checkpoint_json_value)
    return parsed if isinstance(parsed, dict) else None


def _read_checkpoint_end_index(checkpoint: JSONDict | None, *, before_ms: int | None) -> int | None:
    if checkpoint is None or checkpoint.get("before_ms") != before_ms:
        return None
    next_end_index = checkpoint.get("next_end_index")
    return next_end_index if isinstance(next_end_index, int) else None


def _oldest_cached_uid(messages: list[JSONDict]) -> int | None:
    oldest_message = _oldest_message(messages)
    if oldest_message is None:
        return None
    uid_value = oldest_message.get("uid")
    return uid_value if isinstance(uid_value, int) else None


def _oldest_cached_uidl(messages: list[JSONDict]) -> str | None:
    oldest_message = _oldest_message(messages)
    if oldest_message is None:
        return None
    uidl_value = oldest_message.get("uidl")
    if isinstance(uidl_value, str) and uidl_value.strip():
        return uidl_value.strip()
    return None


def _oldest_cached_received_at_ms(messages: list[JSONDict]) -> int | None:
    oldest_message = _oldest_message(messages)
    if oldest_message is None:
        return None
    received_at_ms = oldest_message.get("received_at_ms")
    return received_at_ms if isinstance(received_at_ms, int) else None


def _oldest_message(messages: list[JSONDict]) -> JSONDict | None:
    ordered = [message for message in messages if isinstance(message.get("received_at_ms"), int)]
    if not ordered:
        return None
    return min(ordered, key=_message_received_at_ms)


def _read_batch_count(payload: JSONDict, key: str) -> int:
    value = coerce_optional_non_negative_int_strict(payload.get(key))
    if value is None:
        return 0
    return value


def _message_received_at_ms(message: JSONDict) -> int:
    received_at_ms = message.get("received_at_ms")
    if is_strict_int(received_at_ms):
        return received_at_ms
    return 0
