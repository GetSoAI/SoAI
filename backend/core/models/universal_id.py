"""SoAI - Universal model ID validation helpers [backend/core/models/universal_id.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re

__all__ = (
    "generate_universal_id",
    "is_universal_id",
    "sanitize_model_id_for_universal_id",
)

_UNIVERSAL_ID_SUFFIX_REGEX = r"^[0-9a-f]{16}$"


def is_universal_id(model_id: str) -> bool:
    if not model_id:
        return False
    segments = model_id.split("-")
    if len(segments) < 3:
        return False
    return re.fullmatch(_UNIVERSAL_ID_SUFFIX_REGEX, segments[-1]) is not None


def sanitize_model_id_for_universal_id(model_id: str) -> str:
    return re.sub("[^\\w.-]+", "_", model_id)


def generate_universal_id(plugin: str, stable_model_id: str) -> str | None:
    if not all((plugin, stable_model_id)):
        return None
    sanitized = sanitize_model_id_for_universal_id(stable_model_id)
    hash_input = f"{plugin}:{stable_model_id}".encode()
    hash_suffix = hashlib.sha256(hash_input).hexdigest()[:16]
    return f"{plugin}-{sanitized}-{hash_suffix}"
