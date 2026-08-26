"""SoAI - File Explorer ingest path formatting [backend/features/api/routes/webui/conversation_rag/file_explorer_ingest/path_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("join_virtual_path", "normalize_relative_filename")


def join_virtual_path(parent: str, entry_name: str) -> str:
    parent = str(parent or "").strip()
    if not parent:
        return f"/{entry_name}"
    if parent == "/":
        return f"/{entry_name}"
    normalized = parent.rstrip("/")
    return f"{normalized}/{entry_name}"


def normalize_relative_filename(root_virtual_path: str, virtual_file_path: str) -> str:
    root_prefix = str(root_virtual_path or "").rstrip("/")
    if not root_prefix:
        root_prefix = "/"
    candidate = str(virtual_file_path or "")
    if root_prefix != "/" and candidate.startswith(f"{root_prefix}/"):
        return candidate[len(root_prefix) + 1 :]
    return candidate.lstrip("/")
