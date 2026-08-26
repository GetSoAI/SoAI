"""SoAI - Shared domain account action payloads [backend/features/external_accounts/domain_account_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_action_status",
    "format_account_action_result",
    "format_account_delete_result",
    "format_account_list_result",
)


def format_account_list_result(items: list[JSONDict]) -> JSONDict:
    return {
        "items": items,
        "count": len(items),
    }


def format_account_action_result(
    *,
    account_id: str,
    account_type: str,
    status: str,
    details: JSONDict,
    redirect_url: str | None = None,
) -> JSONDict:
    payload: JSONDict = {
        "ok": True,
        "account_id": account_id,
        "account_type": account_type,
        "status": status,
        "details": details,
    }
    if redirect_url is not None:
        payload["redirect_url"] = redirect_url
    return payload


def format_account_delete_result(*, account_id: str, account_type: str) -> JSONDict:
    return {
        "ok": True,
        "account_id": account_id,
        "account_type": account_type,
    }


def coerce_action_status(value: JSONValue, *, default_value: str) -> str:
    if not isinstance(value, str):
        return default_value
    normalized = value.strip()
    return normalized or default_value
