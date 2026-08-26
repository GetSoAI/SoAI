"""SoAI - Document chunking strategies for RAG vector embeddings [backend/mcp/rag/indexing/chunking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from threading import Lock

import tiktoken
from tiktoken.core import Encoding

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
    shutdown_bounded_pool_executor,
)
from core.errors.exceptions import ValidationError
from core.rag.parameter_validation import validate_chunking_window

__all__ = (
    "DocumentChunk",
    "DocumentChunker",
)


@dataclass(slots=True)
class DocumentChunk:
    index: int
    content: str
    token_count: int
    start_char: int = 0
    end_char: int = 0


class DocumentChunker:
    def __init__(self, blocking_pool: BoundedBlockingPool) -> None:
        self._blocking_pool = blocking_pool
        self._encoding: Encoding | None = None
        self._encoding_lock = Lock()

    def _get_encoding(self) -> Encoding:
        encoding = self._encoding
        if encoding is None:
            with self._encoding_lock:
                encoding = self._encoding
                if encoding is None:
                    encoding = tiktoken.get_encoding("cl100k_base")
                    self._encoding = encoding
        return encoding

    def _encode_text(self, text: str) -> list[int]:
        return self._get_encoding().encode(text, disallowed_special=())

    def _count_tokens(self, text: str) -> int:
        return len(self._encode_text(text))

    def _is_whitespace_only(self, text: str) -> bool:
        if not text:
            return True
        return text.strip() == ""

    def _find_first_non_whitespace_index(
        self,
        text: str,
        *,
        start_index: int,
        end_index: int,
    ) -> int:
        index = int(start_index)
        limit = int(end_index)
        while index < limit and text[index].isspace():
            index += 1
        return index

    def _find_last_non_whitespace_end_index(
        self,
        text: str,
        *,
        start_index: int,
        end_index: int,
    ) -> int:
        index = int(end_index)
        limit = int(start_index)
        while index > limit and text[index - 1].isspace():
            index -= 1
        return index

    def _create_chunk(
        self,
        chunks: list[DocumentChunk],
        content: str,
        start_char: int,
        end_char: int,
        token_count: int | None = None,
    ) -> DocumentChunk:
        return DocumentChunk(
            index=len(chunks),
            content=content,
            token_count=(token_count if token_count is not None else self._count_tokens(content)),
            start_char=start_char,
            end_char=end_char,
        )

    async def chunk(
        self,
        content: str,
        strategy: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[DocumentChunk]:
        validate_chunking_window(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=strategy,
        )
        return await run_bounded_blocking_call(
            self._blocking_pool,
            self._chunk_sync,
            content,
            strategy,
            chunk_size,
            chunk_overlap,
            total_timeout_sec=300.0,
        )

    def shutdown(self) -> None:
        shutdown_bounded_pool_executor(self._blocking_pool)

    def _chunk_sync(
        self,
        content: str,
        strategy: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[DocumentChunk]:
        if strategy == "token_based":
            return self._token_based_chunking(content, chunk_size, chunk_overlap)
        if strategy == "fixed_size":
            return self._fixed_size_chunking(content, chunk_size, chunk_overlap)
        if strategy == "paragraph":
            return self._paragraph_chunking(content, chunk_size)
        if strategy == "semantic":
            overlap_sentences = 0 if chunk_overlap == 0 else max(1, chunk_overlap // 20)
            return self._semantic_chunking(content, chunk_size, overlap_sentences)
        raise ValidationError(f"Unknown chunking strategy: {strategy}")

    def _token_based_chunking(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[DocumentChunk]:
        encoding = self._get_encoding()
        tokens = self._encode_text(content)
        chunks: list[DocumentChunk] = []
        char_offset = 0
        stride = chunk_size - chunk_overlap
        for index in range(0, len(tokens), stride):
            chunk_tokens = tokens[index : index + chunk_size]
            chunk_text = encoding.decode(chunk_tokens)
            start_char = char_offset
            end_char = char_offset + len(chunk_text)
            chunks.append(
                DocumentChunk(
                    index=len(chunks),
                    content=chunk_text,
                    token_count=len(chunk_tokens),
                    start_char=start_char,
                    end_char=end_char,
                ),
            )
            if index + chunk_size < len(tokens):
                overlap_tokens = tokens[index + stride : index + chunk_size]
                overlap_text = encoding.decode(overlap_tokens)
                char_offset += len(chunk_text) - len(overlap_text)
            else:
                char_offset += len(chunk_text)
        return chunks

    def _fixed_size_chunking(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for index in range(0, len(content), chunk_size - chunk_overlap):
            chunk_text = content[index : index + chunk_size]
            chunks.append(self._create_chunk(chunks, chunk_text, index, index + len(chunk_text)))
        return chunks

    def _paragraph_chunking(self, content: str, max_chunk_size: int) -> list[DocumentChunk]:
        paragraphs = content.split("\n\n")
        chunks: list[DocumentChunk] = []
        current_chunk: list[str] = []
        current_size = 0
        char_position = 0
        for paragraph in paragraphs:
            para_size = len(paragraph)
            separator_size = 2 if current_chunk else 0
            if current_size + separator_size + para_size > max_chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    self._create_chunk(
                        chunks,
                        chunk_text,
                        char_position,
                        char_position + len(chunk_text),
                    ),
                )
                char_position += len(chunk_text) + 2
                current_chunk = []
                current_size = 0
            current_chunk.append(paragraph)
            current_size += para_size + (2 if len(current_chunk) > 1 else 0)
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                self._create_chunk(
                    chunks,
                    chunk_text,
                    char_position,
                    char_position + len(chunk_text),
                ),
            )
        return chunks

    def _semantic_chunking(
        self,
        content: str,
        max_chunk_size: int,
        overlap_sentences: int = 1,
    ) -> list[DocumentChunk]:
        sentence_endings = re.compile("(?<=[.!?])\\s+(?=[A-Z])|(?<=\\n)\\s*(?=\\n)")
        if self._is_whitespace_only(content):
            return [self._create_chunk([], content, 0, len(content))]
        segment_spans: list[tuple[int, int]] = []
        segment_start = 0
        for match in sentence_endings.finditer(content):
            match_start = int(match.start())
            match_end = int(match.end())
            segment_end = max(match_start, match_end)
            if segment_end < segment_start:
                continue
            segment_spans.append((segment_start, segment_end))
            segment_start = match_end
        if segment_start < len(content):
            segment_spans.append((segment_start, len(content)))
        segments: list[tuple[int, int, int, int]] = []
        for raw_start, raw_end in segment_spans:
            trim_start = self._find_first_non_whitespace_index(
                content,
                start_index=raw_start,
                end_index=raw_end,
            )
            trim_end = self._find_last_non_whitespace_end_index(
                content,
                start_index=raw_start,
                end_index=raw_end,
            )
            if trim_start >= trim_end:
                continue
            segments.append((raw_start, raw_end, trim_start, trim_end))
        if not segments:
            return [self._create_chunk([], content, 0, len(content))]
        chunks: list[DocumentChunk] = []
        current_segments: list[tuple[int, int, int, int]] = []
        current_trim_start = 0
        current_trim_end = 0

        def _flush_current_segments() -> None:
            nonlocal current_segments
            nonlocal current_trim_start
            nonlocal current_trim_end
            if not current_segments:
                return
            chunk_start = int(current_trim_start)
            chunk_end = int(current_trim_end)
            chunk_text = content[chunk_start:chunk_end]
            chunks.append(self._create_chunk(chunks, chunk_text, chunk_start, chunk_end))
            effective_overlap = min(
                int(overlap_sentences),
                max(0, len(current_segments) - 1),
            )
            if effective_overlap > 0:
                current_segments = current_segments[-effective_overlap:]
                current_trim_start = current_segments[0][2]
                current_trim_end = current_segments[-1][3]
                return
            current_segments = []
            current_trim_start = 0
            current_trim_end = 0

        for raw_start, raw_end, trim_start, trim_end in segments:
            segment_size = int(trim_end) - int(trim_start)
            if segment_size > int(max_chunk_size):
                _flush_current_segments()
                split_start = int(trim_start)
                split_limit = int(trim_end)
                while split_start < split_limit:
                    split_end = min(split_limit, split_start + int(max_chunk_size))
                    split_text = content[split_start:split_end]
                    trimmed_text = split_text.rstrip()
                    if trimmed_text:
                        effective_end = split_start + len(trimmed_text)
                        chunks.append(
                            self._create_chunk(chunks, trimmed_text, split_start, effective_end),
                        )
                        split_start = effective_end
                        continue
                    split_start = split_end
                continue
            next_trim_start = int(current_trim_start) if current_segments else int(trim_start)
            next_trim_end = int(trim_end)
            next_size = next_trim_end - next_trim_start
            if next_size > int(max_chunk_size) and current_segments:
                _flush_current_segments()
                next_trim_start = int(trim_start)
                next_trim_end = int(trim_end)
            current_segments.append((raw_start, raw_end, trim_start, trim_end))
            current_trim_start = next_trim_start
            current_trim_end = next_trim_end
        _flush_current_segments()
        return chunks
