"""SoAI - Plugin SDK Hugging Face input normalization [backend/plugin_sdk/hf/normalize.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from plugin_sdk.hf.types import HuggingFaceReference

__all__ = (
    "HuggingFaceReference",
    "normalize_hf_model_input",
)


def normalize_hf_model_input(value: str) -> tuple[str, str | None]:
    raw = value.strip()
    if not raw:
        return (raw, None)
    candidate = raw
    lower = raw.lower()
    prefix = "huggingface.co/"
    if lower.startswith(prefix):
        candidate = raw[len(prefix) :]
    elif lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
        default_port = "443" if parsed.scheme == "https" else "80"
        if parsed.netloc.lower() in ("huggingface.co", f"huggingface.co:{default_port}"):
            candidate = parsed.path
        else:
            return (raw, None)
    candidate = candidate.strip("/")
    if not candidate:
        return (raw, None)
    segments = [unquote(segment).strip() for segment in candidate.split("/") if segment.strip()]
    if len(segments) < 2:
        return (raw, None)
    repo_id = "/".join(segments[:2])
    remainder = segments[2:]
    if remainder:
        first = remainder[0].lower()
        if first in {"blob", "tree", "resolve", "raw"}:
            remainder = remainder[1:]
    if remainder:
        head_lower = remainder[0].lower()
        if head_lower in {"main", "master"} or re.fullmatch("[0-9a-f]{40}", head_lower):
            remainder = remainder[1:]
    if not remainder:
        return (repo_id, None)
    file_path = "/".join(remainder)
    return (repo_id, file_path)
