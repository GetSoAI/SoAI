"""SoAI - WAV metadata extraction helpers [backend/core/openai/wav_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import struct

__all__ = ("resolve_wav_duration_seconds",)


def resolve_wav_duration_seconds(header: bytes | bytearray | memoryview) -> float | None:
    header_bytes = bytes(header)
    if len(header_bytes) < 44 or header_bytes[0:4] != b"RIFF" or header_bytes[8:12] != b"WAVE":
        return None
    offset = 12
    channels: int | None = None
    sample_rate: int | None = None
    bits_per_sample: int | None = None
    data_size: int | None = None
    while offset + 8 <= len(header_bytes):
        chunk_id = header_bytes[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", header_bytes, offset + 4)[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + int(chunk_size)
        if chunk_id == b"fmt " and chunk_size >= 16 and chunk_start + 16 <= len(header_bytes):
            channels = struct.unpack_from("<H", header_bytes, chunk_start + 2)[0]
            sample_rate = struct.unpack_from("<I", header_bytes, chunk_start + 4)[0]
            bits_per_sample = struct.unpack_from("<H", header_bytes, chunk_start + 14)[0]
        elif chunk_id == b"data":
            data_size = int(chunk_size)
        if (
            channels is not None
            and sample_rate is not None
            and bits_per_sample is not None
            and data_size is not None
        ):
            return _duration_from_pcm_data_size(
                data_size=data_size,
                channels=channels,
                sample_rate=sample_rate,
                bits_per_sample=bits_per_sample,
            )
        if chunk_end > len(header_bytes):
            break
        offset = chunk_end + (chunk_size % 2)
    return None


def _duration_from_pcm_data_size(
    *,
    data_size: int,
    channels: int,
    sample_rate: int,
    bits_per_sample: int,
) -> float | None:
    if data_size <= 0 or channels <= 0 or sample_rate <= 0 or bits_per_sample <= 0:
        return None
    bytes_per_sample = bits_per_sample / 8.0
    bytes_per_second = float(sample_rate) * float(channels) * bytes_per_sample
    if bytes_per_second <= 0.0:
        return None
    return float(data_size) / bytes_per_second
