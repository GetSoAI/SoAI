"""SoAI - WebUI SoAI path link token codec [backend/core/workspaces/soai_path_link_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote

from core.errors.exceptions import ValidationError
from core.network.percent_encoding import is_valid_percent_encoding

__all__ = (
    "SOAI_PATH_TOKEN_PREFIX",
    "DecodedSoaiPathToken",
    "build_soai_path_token",
    "extract_soai_path_tokens",
    "strip_soai_path_tokens",
)

SOAI_PATH_TOKEN_PREFIX = "[[soai:path:"
_SOAI_PATH_TOKEN_SUFFIX = "]]"
_TOKEN_BODY_SEPARATOR = "|"
_MAX_TOKEN_LENGTH = 4096
_MAX_VIRTUAL_PATH_LENGTH = 2048
_MAX_LABEL_LENGTH = 256


@dataclass(frozen=True, slots=True)
class DecodedSoaiPathToken:
    token: str
    occurrence_index: int
    virtual_path: str
    label: str | None
    start_index: int
    end_index: int


def _validate_percent_encoding(value: str, *, label: str) -> None:
    if not is_valid_percent_encoding(value):
        raise ValidationError(f"SoAI path link {label} contains malformed percent encoding.")


def _decode_component(value: str, *, label: str) -> str:
    _validate_percent_encoding(value, label=label)
    try:
        decoded = unquote(value, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise ValidationError(f"SoAI path link {label} contains invalid UTF-8.") from exception
    if quote(decoded, safe="") != value:
        raise ValidationError(f"SoAI path link {label} is not canonically encoded.")
    if "\x00" in decoded:
        raise ValidationError(f"SoAI path link {label} contains a NUL byte.")
    return decoded


def _decode_virtual_path(value: str) -> str:
    virtual_path = _decode_component(value, label="path")
    if not virtual_path:
        raise ValidationError("SoAI path link path is required.")
    if not virtual_path.startswith("/"):
        raise ValidationError("SoAI path link path must be absolute.")
    if len(virtual_path) > _MAX_VIRTUAL_PATH_LENGTH:
        raise ValidationError("SoAI path link path is too long.")
    return virtual_path


def _decode_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = _decode_component(value, label="label")
    if not label:
        return None
    if len(label) > _MAX_LABEL_LENGTH:
        raise ValidationError("SoAI path link label is too long.")
    if any(ord(character) < 32 for character in label):
        raise ValidationError("SoAI path link label contains a control character.")
    return label


def _decode_token(
    token: str,
    *,
    occurrence_index: int,
    start_index: int,
    end_index: int,
) -> DecodedSoaiPathToken:
    if len(token) > _MAX_TOKEN_LENGTH:
        raise ValidationError("SoAI path link token is too long.")
    body = token[len(SOAI_PATH_TOKEN_PREFIX) : -len(_SOAI_PATH_TOKEN_SUFFIX)]
    path_payload, separator, label_payload = body.partition(_TOKEN_BODY_SEPARATOR)
    if not path_payload:
        raise ValidationError("SoAI path link path is required.")
    return DecodedSoaiPathToken(
        token=token,
        occurrence_index=occurrence_index,
        virtual_path=_decode_virtual_path(path_payload),
        label=_decode_label(label_payload if separator else None),
        start_index=start_index,
        end_index=end_index,
    )


def extract_soai_path_tokens(text: str) -> list[DecodedSoaiPathToken]:
    tokens: list[DecodedSoaiPathToken] = []
    search_index = 0
    while True:
        start_index = text.find(SOAI_PATH_TOKEN_PREFIX, search_index)
        if start_index < 0:
            return tokens
        end_index = text.find(_SOAI_PATH_TOKEN_SUFFIX, start_index + len(SOAI_PATH_TOKEN_PREFIX))
        if end_index < 0:
            raise ValidationError("SoAI path link token is missing its closing delimiter.")
        token_end_index = end_index + len(_SOAI_PATH_TOKEN_SUFFIX)
        token = text[start_index:token_end_index]
        tokens.append(
            _decode_token(
                token,
                occurrence_index=len(tokens),
                start_index=start_index,
                end_index=token_end_index,
            ),
        )
        search_index = token_end_index


def strip_soai_path_tokens(text: str) -> str:
    if SOAI_PATH_TOKEN_PREFIX not in text:
        return text.strip()
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        start_index = text.find(SOAI_PATH_TOKEN_PREFIX, cursor)
        if start_index < 0:
            parts.append(text[cursor:])
            break
        parts.append(text[cursor:start_index])
        end_index = text.find(
            _SOAI_PATH_TOKEN_SUFFIX,
            start_index + len(SOAI_PATH_TOKEN_PREFIX),
        )
        if end_index < 0:
            break
        cursor = end_index + len(_SOAI_PATH_TOKEN_SUFFIX)
    return " ".join("".join(parts).split())


def build_soai_path_token(*, virtual_path: str, label: str | None = None) -> str:
    decoded_path = _decode_virtual_path(quote(virtual_path, safe=""))
    encoded_path = quote(decoded_path, safe="")
    if label is None or not label.strip():
        return f"{SOAI_PATH_TOKEN_PREFIX}{encoded_path}{_SOAI_PATH_TOKEN_SUFFIX}"
    decoded_label = _decode_label(quote(label, safe=""))
    return f"{SOAI_PATH_TOKEN_PREFIX}{encoded_path}|{quote(decoded_label or '', safe='')}{_SOAI_PATH_TOKEN_SUFFIX}"
