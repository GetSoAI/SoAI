"""SoAI - Preview-contract reason code definitions [backend/core/preview_contract/preview_contract_reason_codes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("is_preview_contract_reason_code",)

PREVIEW_CONTRACT_REASON_CODES: tuple[str, ...] = (
    "missing_preview_reference",
    "noncanonical_reference_syntax",
    "absolute_path_preview_scope_unavailable",
    "invalid_remote_url",
    "invalid_absolute_path_reference",
    "invalid_virtual_path_reference",
)


def is_preview_contract_reason_code(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return value in PREVIEW_CONTRACT_REASON_CODES
