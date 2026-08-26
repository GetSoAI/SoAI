"""SoAI - Browser download flow hint payloads [backend/mcp/tools/browser/download_flow_hints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = ("build_download_flow_hints",)


def build_download_flow_hints(
    *,
    url: str,
    profile: str | None = None,
    session_scope: str | None = None,
    include_navigate: bool = True,
) -> JSONDict:
    normalized_url = str(url or "").strip()
    args: JSONDict = {
        "action": "url",
        "url": normalized_url,
        "include_snapshot": False,
    }
    downloads_args: JSONDict = {}
    if profile is not None and profile.strip():
        normalized_profile = profile.strip()
        args["profile"] = normalized_profile
        downloads_args["profile"] = normalized_profile
    if session_scope is not None and session_scope.strip():
        normalized_scope = session_scope.strip()
        args["session_scope"] = normalized_scope
        downloads_args["session_scope"] = normalized_scope
    output: JSONDict = {
        "browser_downloads_hint": (
            "Browser-managed downloads are saved asynchronously. Call browser_downloads until the "
            "entry is completed with file_path, or terminally canceled/failed."
        ),
        "browser_downloads_args": downloads_args,
    }
    if include_navigate:
        output["browser_navigate_hint"] = (
            "This URL triggers a browser-managed download. Use read_document with the URL when the "
            "document content needs to be fetched through SoAI's reserved download path."
        )
        output["browser_navigate_args"] = args
    return output
