"""SoAI - Preview-contract capability system message builder [backend/features/api/runtime/preview_contract_capability_message.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("build_preview_contract_capability_system_message",)

_PREVIEW_CAPABILITY_PREFIX = "<soai_preview_capability>"


def build_preview_contract_capability_system_message() -> str:
    lines = [
        _PREVIEW_CAPABILITY_PREFIX,
        "The SoAI WebUI can render assistant-authored previews from canonical references in the final assistant message body using one of these forms:",
        "- [[preview:absolute_path:<absolute path>]]",
        "- [[preview:virtual_path:<virtual path>]]",
        "- [[preview:remote_url:<https URL>]]",
        "Use absolute_path only for real absolute OS filesystem paths on the SoAI host, such as /srv/files/report.pdf.",
        "Use virtual_path only for File Explorer virtual paths rooted at /, such as /folder/file.txt.",
        "Do not put an OS filesystem path into virtual_path. If the File Explorer root is /srv/files, the OS path /srv/files/reports/a.md maps to virtual_path /reports/a.md.",
        "For requests to view, inspect, or open content through the WebUI, include one or more canonical preview references in the visible assistant response body near the end of the final assistant message.",
        "Do not place preview references inside fenced code blocks, backticks, tool calls, tool arguments, or tool results.",
        "</soai_preview_capability>",
    ]
    return "\n".join(lines)
