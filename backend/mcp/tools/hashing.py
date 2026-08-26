"""SoAI - MCP hash generator tool implementation [backend/mcp/tools/hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.serialization.base64_values import encode_base64_ascii
from mcp.tools.argument_fields import (
    reject_unexpected_parameters,
    require_string,
    require_string_choice,
)
from mcp.tools.error import get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_hash",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"text", "algorithm", "encoding"})


async def tool_hash(_utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    text = require_string(get_arg(arguments, "text"), key="text")
    encoding_raw = arguments.get("encoding", "hex")
    encoding = require_string_choice(encoding_raw, key="encoding", choices=("hex", "base64"))
    algorithm_raw = arguments.get("algorithm", "sha256")
    algorithm = require_string_choice(
        algorithm_raw,
        key="algorithm",
        choices=("md5", "sha1", "sha256", "sha512"),
    )
    hash_funcs = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    hash_bytes = hash_funcs[algorithm](text.encode("utf-8")).digest()
    hash_value = hash_bytes.hex() if encoding == "hex" else encode_base64_ascii(hash_bytes)
    return {
        "hash": hash_value,
        "algorithm": algorithm,
        "encoding": encoding,
        "input_length": len(text),
    }
