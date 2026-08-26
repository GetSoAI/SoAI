"""SoAI - Provider-backed model metadata helpers [backend/core/models/provider_backing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("get_model_provider_id", "is_provider_backed_model")


def get_model_provider_id(model_info: Mapping[str, JSONValue]) -> str | None:
    return coerce_optional_trimmed_str(model_info.get("provider_id"))


def is_provider_backed_model(model_info: Mapping[str, JSONValue]) -> bool:
    return get_model_provider_id(model_info) is not None
