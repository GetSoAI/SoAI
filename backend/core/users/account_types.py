"""SoAI - WebUI account type contract [backend/core/users/account_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from typing import Literal

    type WebuiAccountType = Literal["human"]

HUMAN_ACCOUNT_TYPE: WebuiAccountType = "human"
WEBUI_ACCOUNT_TYPES: tuple[WebuiAccountType, ...] = (HUMAN_ACCOUNT_TYPE,)


def webui_account_type_sql_values() -> str:
    return ", ".join(f"'{value}'" for value in WEBUI_ACCOUNT_TYPES)


def require_webui_account_type(value: str) -> WebuiAccountType:
    if value == HUMAN_ACCOUNT_TYPE:
        return HUMAN_ACCOUNT_TYPE
    raise ValidationError("WebUI account type is invalid.")


__all__ = (
    "HUMAN_ACCOUNT_TYPE",
    "WEBUI_ACCOUNT_TYPES",
    "require_webui_account_type",
    "webui_account_type_sql_values",
)
