"""SoAI - Status preview payload generation [backend/features/assistant_timeline/status_preview_payload_generation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from features.assistant_timeline.models import StatusPreviewRequest
from features.assistant_timeline.status_preview_payload_variants import (
    phase_preview_key_variants,
    tool_preview_key_variants_detail,
    tool_preview_key_variants_plain,
    web_search_preview_key_variants_detail,
    web_search_preview_key_variants_plain,
)
from features.assistant_timeline.status_preview_tool_variants import (
    browser_preview_key_variants_detail,
    browser_preview_key_variants_plain,
    memory_preview_key_variants_detail,
    memory_preview_key_variants_plain,
    vault_preview_key_variants_detail,
    vault_preview_key_variants_plain,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("generate_status_preview_payload",)


def _select_variant_index(
    identity: str,
    variants: tuple[str, ...],
    current_preview_key: str,
) -> int:
    if len(variants) <= 1:
        return 0
    if current_preview_key:
        for index, variant in enumerate(variants):
            if variant == current_preview_key:
                return (index + 1) % len(variants)
    digest = sha256(f"{identity}|{len(variants)}".encode()).digest()
    return digest[0] % len(variants)


def _build_preview_args(tool_detail: str | None) -> JSONDict | None:
    normalized_detail = str(tool_detail or "").strip()
    if not normalized_detail:
        return None
    return {"detail": normalized_detail}


def _select_tool_preview_payload(
    tool_name: str,
    tool_detail: str | None,
    current_preview_key: str,
) -> tuple[str, JSONDict | None] | None:
    normalized_tool = str(tool_name or "").strip()
    if not normalized_tool:
        return None
    normalized_detail = str(tool_detail or "").strip() or None
    if normalized_tool == "ask_user":
        normalized_detail = None
    if normalized_tool.startswith("browser_"):
        if normalized_detail:
            browser_detail_variants = browser_preview_key_variants_detail()
            index = _select_variant_index(
                "browser",
                browser_detail_variants,
                current_preview_key,
            )
            return (browser_detail_variants[index], _build_preview_args(normalized_detail))
        browser_plain_variants = browser_preview_key_variants_plain()
        index = _select_variant_index("browser", browser_plain_variants, current_preview_key)
        return (browser_plain_variants[index], None)
    if normalized_tool.startswith("memory_"):
        if normalized_detail:
            memory_detail_variants = memory_preview_key_variants_detail()
            index = _select_variant_index(
                "memory",
                memory_detail_variants,
                current_preview_key,
            )
            return (memory_detail_variants[index], _build_preview_args(normalized_detail))
        memory_plain_variants = memory_preview_key_variants_plain()
        index = _select_variant_index("memory", memory_plain_variants, current_preview_key)
        return (memory_plain_variants[index], None)
    if normalized_tool.startswith("vault_"):
        if normalized_detail:
            vault_detail_variants = vault_preview_key_variants_detail()
            index = _select_variant_index(
                "vault",
                vault_detail_variants,
                current_preview_key,
            )
            return (vault_detail_variants[index], _build_preview_args(normalized_detail))
        vault_plain_variants = vault_preview_key_variants_plain()
        index = _select_variant_index("vault", vault_plain_variants, current_preview_key)
        return (vault_plain_variants[index], None)
    if normalized_tool.startswith("web_search_"):
        if normalized_detail:
            web_search_detail_variants = web_search_preview_key_variants_detail()
            index = _select_variant_index(
                "web_search",
                web_search_detail_variants,
                current_preview_key,
            )
            return (web_search_detail_variants[index], _build_preview_args(normalized_detail))
        web_search_plain_variants = web_search_preview_key_variants_plain()
        index = _select_variant_index("web_search", web_search_plain_variants, current_preview_key)
        return (web_search_plain_variants[index], None)

    plain_variants_map = tool_preview_key_variants_plain()
    plain_variants_value = plain_variants_map.get(normalized_tool)
    if plain_variants_value is None:
        return None
    resolved_plain_variants: tuple[str, ...] = plain_variants_value
    if normalized_detail:
        detail_variants_value = tool_preview_key_variants_detail().get(normalized_tool)
        if detail_variants_value is not None and len(detail_variants_value) == len(
            resolved_plain_variants,
        ):
            resolved_detail_variants: tuple[str, ...] = detail_variants_value
            index = _select_variant_index(
                normalized_tool,
                resolved_detail_variants,
                current_preview_key,
            )
            return (resolved_detail_variants[index], _build_preview_args(normalized_detail))
    index = _select_variant_index(
        normalized_tool,
        resolved_plain_variants,
        current_preview_key,
    )
    return (resolved_plain_variants[index], None)


def _select_phase_preview_payload(
    phase: str,
    current_preview_key: str,
) -> tuple[str, JSONDict | None] | None:
    normalized = str(phase or "").strip().lower()
    variants = phase_preview_key_variants().get(normalized)
    if variants is None:
        return None
    index = _select_variant_index(normalized, variants, current_preview_key)
    return (variants[index], None)


def generate_status_preview_payload(
    request: StatusPreviewRequest,
) -> tuple[str, JSONDict | None] | None:
    current_preview_key = (
        str(request.current_shown_label or "").strip().split("|", maxsplit=1)[0].strip()
    )
    tool_snapshot = request.latest_completed_tool
    if tool_snapshot is not None:
        normalized_tool_name = str(tool_snapshot.tool_name or "").strip()
        if normalized_tool_name:
            return _select_tool_preview_payload(
                normalized_tool_name,
                tool_snapshot.detail,
                current_preview_key,
            )
    return _select_phase_preview_payload(request.current_phase, current_preview_key)
