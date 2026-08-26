"""SoAI - MCP utility tool definitions: hash, base64 [backend/mcp/tools/utility_tool_definitions/crypto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CODE, ICON_HASH

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_crypto_tool_definitions",)


def build_crypto_tool_definitions() -> dict[str, JSONDict]:
    return {
        "hash": {
            "title": "Hash Generator",
            "description": "Generate cryptographic hashes (MD5, SHA1, SHA256, SHA512) of text input",
            "icons": [build_tool_icon_entry(ICON_HASH)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string", "description": "Text to hash"},
                    "algorithm": {
                        "type": "string",
                        "description": "Hash algorithm to use (default: sha256)",
                        "enum": ["md5", "sha1", "sha256", "sha512"],
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Output encoding: hex (default) or base64",
                    },
                },
                "required": ["text"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "hash": {
                        "type": "string",
                        "description": "The computed hash value",
                    },
                    "algorithm": {"type": "string"},
                    "encoding": {"type": "string"},
                    "input_length": {"type": "integer"},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
        "base64": {
            "title": "Base64 Encoder/Decoder",
            "description": "Encode or decode text using Base64, Base64URL, or Base32.",
            "icons": [build_tool_icon_entry(ICON_CODE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation to perform",
                        "enum": ["encode", "decode"],
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to encode or decode",
                    },
                    "variant": {
                        "type": "string",
                        "description": "Encoding variant: base64 (default), base64url, or base32",
                    },
                },
                "required": ["operation", "text"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "Encoded or decoded result",
                    },
                    "operation": {"type": "string"},
                    "variant": {"type": "string"},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
