"""SoAI - Browser tool digests for context compaction [backend/features/agent/runtime/context_compaction/tool_digests_browser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.agent.runtime.context_compaction.browser_digest import (
    digest_browser_snapshot_payload,
)
from features.agent.runtime.context_compaction.internal_protocols import (
    TruncateLineProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("digest_browser_tool_exchange",)


def digest_browser_tool_exchange(
    tool_name: str,
    tool_arguments: JSONDict | None,
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str] | None:
    if tool_name == "browser_status":
        url_value = tool_result.get("active_url")
        title_value = tool_result.get("active_title")
        profile_value = tool_result.get("profile")
        scope_value = tool_result.get("session_scope")
        persistence_value = tool_result.get("persistence_mode")
        status_parts: list[str] = []
        if isinstance(profile_value, str) and profile_value.strip():
            status_parts.append(f"profile={truncate_line(profile_value)}")
        if isinstance(scope_value, str) and scope_value.strip():
            status_parts.append(f"scope={truncate_line(scope_value)}")
        if isinstance(persistence_value, str) and persistence_value.strip():
            status_parts.append(f"persist={truncate_line(persistence_value)}")
        if isinstance(title_value, str) and title_value.strip():
            status_parts.append(f"title={truncate_line(title_value)}")
        if isinstance(url_value, str) and url_value.strip():
            status_parts.append(f"url={truncate_line(url_value)}")
        return [f"browser_status: {'; '.join(status_parts)}"] if status_parts else []
    if tool_name == "browser_snapshot":
        return digest_browser_snapshot_payload(tool_result)
    if tool_name == "browser_navigate":
        url_value = tool_result.get("url")
        title_value = tool_result.get("title")
        parts: list[str] = []
        if isinstance(title_value, str) and title_value.strip():
            parts.append(f"title={truncate_line(title_value)}")
        if isinstance(url_value, str) and url_value.strip():
            parts.append(f"url={truncate_line(url_value)}")
        if not parts:
            return []
        return [f"{tool_name} page: {'; '.join(parts)}"]
    if tool_name == "browser_type":
        error_value = tool_result.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return [f"browser_type error: {truncate_line(error_value)}"]
        if tool_arguments is None:
            return []
        text_value = tool_arguments.get("text")
        if not isinstance(text_value, str) or not text_value.strip():
            return []
        submit_value = tool_arguments.get("submit")
        submit_text = " submit" if isinstance(submit_value, bool) and submit_value else ""
        return [f"browser_type input{submit_text}: <redacted len={len(text_value)}>"]
    if tool_name == "browser_press_key":
        error_value = tool_result.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return [f"browser_press_key error: {truncate_line(error_value)}"]
        if tool_arguments is None:
            return []
        key_value = tool_arguments.get("key")
        if not isinstance(key_value, str) or not key_value.strip():
            return []
        return [f"browser_press_key: {truncate_line(key_value)}"]
    if tool_name == "browser_profiles":
        default_profile = tool_result.get("default_profile")
        profiles = tool_result.get("profiles")
        if not isinstance(default_profile, str):
            return []
        if not isinstance(profiles, list):
            return [f"browser_profiles default_profile={truncate_line(default_profile)}"]
        names: list[str] = []
        for item in profiles:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        suffix = f"; profiles={truncate_line(','.join(names))}" if names else ""
        return [f"browser_profiles default_profile={truncate_line(default_profile)}{suffix}"]
    if tool_name == "browser_dialog":
        if tool_arguments is not None:
            action = tool_arguments.get("action")
            if isinstance(action, str) and action.strip():
                return [f"browser_dialog action={truncate_line(action.strip())}"]
        return ["browser_dialog"]
    if tool_name == "browser_pdf":
        bytes_value = tool_result.get("bytes")
        sha_value = tool_result.get("sha256")
        pdf_parts: list[str] = []
        if is_strict_int(bytes_value):
            pdf_parts.append(f"bytes={bytes_value}")
        if isinstance(sha_value, str) and sha_value.strip():
            pdf_parts.append(f"sha256={truncate_line(sha_value)}")
        return [f"browser_pdf: {'; '.join(pdf_parts)}"] if pdf_parts else ["browser_pdf"]
    return None
