"""SoAI - Status preview tool variant keys [backend/features/assistant_timeline/status_preview_tool_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()


def browser_preview_key_variants_plain() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.browser.1",
        "chat.stream.preview.tools.browser.2",
    )


def browser_preview_key_variants_detail() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.browser.detail.1",
        "chat.stream.preview.tools.browser.detail.2",
    )


def memory_preview_key_variants_plain() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.memory.1",
        "chat.stream.preview.tools.memory.2",
    )


def memory_preview_key_variants_detail() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.memory.detail.1",
        "chat.stream.preview.tools.memory.detail.2",
    )


def vault_preview_key_variants_plain() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.vault.1",
        "chat.stream.preview.tools.vault.2",
    )


def vault_preview_key_variants_detail() -> tuple[str, ...]:
    return (
        "chat.stream.preview.tools.vault.detail.1",
        "chat.stream.preview.tools.vault.detail.2",
    )
