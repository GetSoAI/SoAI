"""SoAI - Bounded ZIP payload decoding with actual size and stream integrity checks [backend/core/archives/zip_bounded_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import bz2
import io
import lzma
import struct
import zipfile
import zlib

from core.archives.constants import CHUNK_READ_SIZE
from core.archives.resource_limits import ArchivePlanningBudget, encoded_metadata_size
from core.errors.exceptions import ValidationError
from core.validation.requirements import require_non_negative_exact_int

__all__ = ("read_bounded_zip_member",)

_LOCAL_HEADER_FORMAT = "<4s5H3L2H"


def read_bounded_zip_member(
    source: io.BufferedIOBase | io.RawIOBase,
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    *,
    metadata_budget: ArchivePlanningBudget,
    maximum_bytes: int,
    maximum_decoder_memory_bytes: int,
    aggregate_metadata_budget: ArchivePlanningBudget | None = None,
) -> bytes:
    maximum = require_non_negative_exact_int(
        maximum_bytes,
        type_message="ZIP expanded byte limit must be an integer.",
        range_message="ZIP expanded byte limit must not be negative.",
    )
    if member.flag_bits & (0x1 | 0x20 | 0x40):
        raise ValidationError(
            "Encrypted or patched ZIP members are unsupported.",
            details={"archive_reason": "unsupported"},
        )
    if member.file_size > maximum:
        raise ValidationError(
            "ZIP member exceeds its expanded size limit.",
            details={
                "archive_resource": "expanded_bytes",
                "measured": member.file_size,
                "limit": maximum,
            },
        )
    archive.open(member).close()
    source.seek(member.header_offset)
    header_size = struct.calcsize(_LOCAL_HEADER_FORMAT)
    header = source.read(header_size)
    if len(header) != header_size:
        raise zipfile.BadZipFile("ZIP local header is truncated.")
    signature, _, flags, compression, _, _, _, _, _, name_size, extra_size = struct.unpack(
        _LOCAL_HEADER_FORMAT, header
    )
    if (
        signature != b"PK\x03\x04"
        or flags != member.flag_bits
        or compression != member.compress_type
    ):
        raise zipfile.BadZipFile("ZIP local and central headers disagree.")
    metadata_budget.add_member(
        metadata_bytes=name_size
        + extra_size
        + encoded_metadata_size(member.orig_filename, member.extra, member.comment),
        name=member.orig_filename,
    )
    if aggregate_metadata_budget is not None:
        aggregate_metadata_budget.add_local_metadata(name_size + extra_size, member.orig_filename)
    source.seek(name_size + extra_size, 1)
    try:
        content = _decode(source, member, maximum, maximum_decoder_memory_bytes)
    except (zlib.error, lzma.LZMAError, OSError, EOFError) as exception:
        raise zipfile.BadZipFile("ZIP compressed member is invalid.") from exception
    if len(content) != member.file_size or zlib.crc32(content) != member.CRC:
        raise zipfile.BadZipFile("ZIP member size or CRC is inconsistent.")
    return content


def _decode(
    source: io.BufferedIOBase | io.RawIOBase,
    member: zipfile.ZipInfo,
    maximum: int,
    maximum_decoder_memory_bytes: int,
) -> bytes:
    if member.compress_type == zipfile.ZIP_STORED:
        if member.compress_size > maximum:
            raise ValidationError(
                "ZIP member exceeds its expanded size limit.",
                details={
                    "archive_resource": "expanded_bytes",
                    "measured": member.compress_size,
                    "limit": maximum,
                },
            )
        content = source.read(member.compress_size)
        if len(content) != member.compress_size:
            raise zipfile.BadZipFile("ZIP compressed member is truncated.")
        return content
    if member.compress_type == zipfile.ZIP_DEFLATED:
        decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        content = bytearray()
        remaining = member.compress_size
        while remaining:
            pending = _read_compressed_chunk(source, remaining)
            remaining -= len(pending)
            while pending:
                content.extend(
                    decoder.decompress(pending, min(CHUNK_READ_SIZE, maximum - len(content) + 1))
                )
                if len(content) > maximum:
                    raise ValidationError(
                        "ZIP member exceeds its expanded size limit.",
                        details={
                            "archive_resource": "expanded_bytes",
                            "measured": len(content),
                            "limit": maximum,
                        },
                    )
                pending = decoder.unconsumed_tail
            if decoder.eof and remaining:
                raise zipfile.BadZipFile("ZIP deflate stream has trailing data.")
        if not decoder.eof or decoder.unused_data:
            raise zipfile.BadZipFile("ZIP deflate stream is truncated or has trailing data.")
        return bytes(content)
    if member.compress_type == zipfile.ZIP_BZIP2:
        return _decode_buffered(
            bz2.BZ2Decompressor(), source, member.compress_size, maximum, require_eof=True
        )
    if member.compress_type == zipfile.ZIP_LZMA:
        prefix = source.read(min(9, member.compress_size))
        if len(prefix) < 9 or int.from_bytes(prefix[2:4], "little") != 5:
            raise zipfile.BadZipFile("ZIP LZMA properties are invalid.")
        properties = prefix[4]
        dictionary_size = int.from_bytes(prefix[5:9], "little")
        if dictionary_size > maximum_decoder_memory_bytes:
            raise ValidationError(
                "ZIP LZMA decoder properties exceed supported limits.",
                details={
                    "archive_resource": "decoder_memory_bytes",
                    "measured": dictionary_size,
                    "limit": maximum_decoder_memory_bytes,
                },
            )
        if properties >= 225:
            raise ValidationError("ZIP LZMA decoder properties exceed supported limits.")
        literal_context = properties % 9
        remainder = properties // 9
        decoder_lzma = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA1,
                    "dict_size": max(dictionary_size, 4096),
                    "lc": literal_context,
                    "lp": remainder % 5,
                    "pb": remainder // 5,
                }
            ],
        )
        return _decode_buffered(
            decoder_lzma,
            source,
            member.compress_size - 9,
            maximum,
            require_eof=bool(member.flag_bits & 0x2),
        )
    raise ValidationError(
        "ZIP member uses unsupported compression.", details={"archive_reason": "unsupported"}
    )


def _decode_buffered(
    decoder: bz2.BZ2Decompressor | lzma.LZMADecompressor,
    source: io.BufferedIOBase | io.RawIOBase,
    remaining: int,
    maximum: int,
    *,
    require_eof: bool,
) -> bytes:
    content = bytearray()
    while remaining or not decoder.needs_input:
        pending = _read_compressed_chunk(source, remaining) if decoder.needs_input else b""
        remaining -= len(pending)
        content.extend(
            decoder.decompress(pending, max_length=min(CHUNK_READ_SIZE, maximum - len(content) + 1))
        )
        if len(content) > maximum:
            raise ValidationError(
                "ZIP member exceeds its expanded size limit.",
                details={
                    "archive_resource": "expanded_bytes",
                    "measured": len(content),
                    "limit": maximum,
                },
            )
        if decoder.eof:
            break
    if (require_eof and not decoder.eof) or remaining or (decoder.eof and decoder.unused_data):
        raise zipfile.BadZipFile("ZIP compressed stream is truncated or has trailing data.")
    return bytes(content)


def _read_compressed_chunk(source: io.BufferedIOBase | io.RawIOBase, remaining: int) -> bytes:
    chunk = source.read(min(CHUNK_READ_SIZE, remaining))
    if not chunk:
        raise zipfile.BadZipFile("ZIP compressed member is truncated.")
    return chunk
