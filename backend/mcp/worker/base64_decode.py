"""SoAI - MCP worker base64 decode operations [backend/mcp/worker/base64_decode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.mcp.argument_validation import require_non_empty_string_value
from core.serialization.base64_values import extract_base64_data_payload
from mcp.worker.transfer import run_local_transfer_with_progress
from mcp.worker.types import BASE64_ALPHABET

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("decode_base64_to_file",)


def _estimate_decoded_size(raw: str, max_bytes: int) -> int:
    compact = "".join(character for character in raw if not character.isspace())
    valid_chars = len(compact)
    max_base64_len = (max_bytes + 2) // 3 * 4
    if valid_chars > max_base64_len:
        raise ValidationError(
            f"Upload too large: base64 length {valid_chars} exceeds {max_base64_len} limit",
        )
    remainder = valid_chars % 4
    if remainder == 1:
        raise ValidationError("Invalid base64 content length")
    explicit_padding = valid_chars - len(compact.rstrip("="))
    if explicit_padding > 2:
        raise ValidationError("Invalid base64 content length")
    if "=" in compact[: valid_chars - explicit_padding]:
        raise ValidationError("Invalid base64 content length")
    if remainder and explicit_padding:
        raise ValidationError("Invalid base64 content length")
    total_padding = explicit_padding if remainder == 0 else 4 - remainder
    return max(0, ((valid_chars + (4 - remainder if remainder else 0)) // 4 * 3) - total_padding)


async def decode_base64_to_file(
    self: MCPWorkerProtocol,
    task_id: str,
    *,
    content_base64: str,
    destination_path: str,
    label: str,
    max_bytes: int,
    progress_start: int,
    progress_end: int,
) -> int:
    normalized_content = require_non_empty_string_value(
        content_base64,
        build_error=ValidationError,
        type_message="content_base64 must be a non-empty string",
        empty_message="content_base64 must be a non-empty string",
    )
    if not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValidationError("max_bytes must be a positive integer")
    raw = extract_base64_data_payload(normalized_content)
    if not raw:
        raise ValidationError("content_base64 must contain base64 payload")
    raw = raw.replace("-", "+").replace("_", "/")
    estimated_size = _estimate_decoded_size(raw, max_bytes)
    if estimated_size <= 0:
        raise ValidationError("Decoded upload is empty.")
    reservation = self.storage_manager.reserve_disk_space(
        path=destination_path,
        required_bytes=estimated_size,
        operation="mcp.worker.decode_base64_to_file.stage_temp",
        details={
            "destination_path": destination_path,
            "label": label,
            "required_bytes": estimated_size,
        },
    )

    def _blocking_decode_with_progress(
        report_callback: Callable[[int, int | None], None],
    ) -> int:
        estimated_total = estimated_size
        valid_chars = 0
        for character in raw:
            if not character.isspace():
                valid_chars += 1
        report_callback(0, estimated_total)
        destination_dir = os.path.dirname(destination_path)
        if destination_dir:
            os.makedirs(destination_dir, exist_ok=True)
        buffer_chars: list[str] = []
        bytes_written = 0
        with open_binary(destination_path, mode="wb") as destination_handle:
            for character in raw:
                if character.isspace():
                    continue
                if character not in BASE64_ALPHABET:
                    raise ValidationError("Invalid base64 content")
                buffer_chars.append(character)
                if len(buffer_chars) >= 65536 and len(buffer_chars) % 4 == 0:
                    decoded = base64.b64decode("".join(buffer_chars), validate=True)
                    with claim_reserved_write(reservation, size_bytes=len(decoded)):
                        destination_handle.write(decoded)
                    bytes_written += len(decoded)
                    if bytes_written > max_bytes:
                        raise ValidationError(f"Upload exceeds limit of {max_bytes} bytes")
                    report_callback(bytes_written, estimated_total)
                    buffer_chars.clear()
            if buffer_chars:
                remainder = len(buffer_chars) % 4
                if remainder == 1:
                    raise ValidationError("Invalid base64 content length")
                if remainder in (2, 3):
                    buffer_chars.extend(["="] * (4 - remainder))
                decoded = base64.b64decode("".join(buffer_chars), validate=True)
                with claim_reserved_write(reservation, size_bytes=len(decoded)):
                    destination_handle.write(decoded)
                bytes_written += len(decoded)
                if bytes_written > max_bytes:
                    raise ValidationError(f"Upload exceeds limit of {max_bytes} bytes")
                report_callback(bytes_written, estimated_total)
        if bytes_written != estimated_size:
            raise ValidationError("Decoded upload size does not match declared reservation.")
        return bytes_written

    try:
        return await run_local_transfer_with_progress(
            self,
            task_id,
            action="Uploading",
            label=label,
            progress_start=progress_start,
            progress_end=progress_end,
            total_bytes=estimated_size,
            transfer_function=_blocking_decode_with_progress,
        )
    finally:
        reservation.release()
