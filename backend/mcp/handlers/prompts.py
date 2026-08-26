"""SoAI - MCP RAG prompt handler implementations [backend/mcp/handlers/prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.mcp.argument_validation import require_non_empty_string_value
from core.mcp.content_envelopes import build_text_prompt_result
from core.prompts.system_prompts import (
    get_text_prompt_v1,
    render_text_prompt_template_v1,
)
from mcp.progress_reporting import require_rag_document_with_conv_id
from mcp.protocol.types import MCPJSONRPCError
from mcp.rag.internal_protocols import MCPRAGInternalProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_mcp_rag_prompt_handlers",
    "build_text_prompt",
)


def _coerce_positive_int_or_raise(arguments: JSONDict, *, key: str, default: int) -> int:
    try:
        return coerce_positive_int(
            arguments.get(key, default),
            default=default,
            minimum=1,
            label=key,
        )
    except ValidationError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception


def build_text_prompt(description: str, prompt_text: str) -> JSONDict:
    return build_text_prompt_result(description=description, text=prompt_text)


def _require_prompt_string(arguments: JSONDict, key: str) -> str:
    return require_non_empty_string_value(
        arguments.get(key),
        build_error=lambda message: MCPJSONRPCError(-32602, message),
        type_message=f"{key} must be a non-empty string",
        empty_message=f"{key} must be a non-empty string",
    )


def build_mcp_rag_prompt_handlers(
    rag: MCPRAGInternalProtocol,
    *,
    require_authenticated_user_id: Callable[[str], int],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONDict]]]:

    async def rag_document_summary(arguments: JSONDict) -> JSONDict:
        user_id = require_authenticated_user_id("RAG document_summary prompt")
        document_id = _require_prompt_string(arguments, "document_id")
        doc, doc_conv_id = await require_rag_document_with_conv_id(rag.database_files, document_id)
        await rag.resolve_conv_id_for_user(doc_conv_id, user_id)
        doc_id_value = doc.get("id")
        if not isinstance(doc_id_value, str) or not doc_id_value:
            raise MCPJSONRPCError(-32602, "Document id is missing")
        max_chunks = _coerce_positive_int_or_raise(arguments, key="max_chunks", default=50)
        chunks_value = await rag.database_files.get_rag_chunks_for_document_page(
            doc_id_value,
            limit=max_chunks,
        )
        chunks = (
            [chunk for chunk in chunks_value if isinstance(chunk, dict)]
            if isinstance(chunks_value, list)
            else []
        )
        context: list[str] = []
        tokens = 0
        for chunk in chunks:
            chunk_index = chunk.get("chunk_index", 0)
            chunk_index_label = chunk_index if isinstance(chunk_index, int) else 0
            chunk_content = chunk.get("content")
            chunk_text = chunk_content if isinstance(chunk_content, str) else ""
            txt = f"[Chunk {chunk_index_label}]\n{chunk_text}"
            if tokens + len(txt) // 4 > 8000:
                break
            context.append(txt)
            tokens += len(txt) // 4
        filename = doc.get("filename")
        file_type = doc.get("file_type")
        total_chunks = doc.get("total_chunks")
        filename_label = filename if isinstance(filename, str) else "unknown"
        file_type_label = file_type if isinstance(file_type, str) else "unknown"
        total_chunks_label = total_chunks if isinstance(total_chunks, int) else 0
        prompt_text = render_text_prompt_template_v1(
            "mcp.rag.document_summary.user_template.v1",
            {
                "RAG_FILENAME": filename_label,
                "RAG_FILE_TYPE": file_type_label,
                "RAG_TOTAL_CHUNKS": str(total_chunks_label),
                "RAG_CONTEXT": "\n".join(context),
            },
        )
        return build_text_prompt(f"Summarize document: {filename_label}", prompt_text)

    async def rag_topic_extraction(arguments: JSONDict) -> JSONDict:
        conv_id = _require_prompt_string(arguments, "conv_id")
        user_id = require_authenticated_user_id("RAG topic_extraction prompt")
        resolved = await rag.resolve_conv_id_for_user(conv_id, user_id)
        docs_value = await rag.database_files.get_rag_documents_for_conversation(
            resolved,
            limit=500,
        )
        docs = (
            [doc for doc in docs_value if isinstance(doc, dict)]
            if isinstance(docs_value, list)
            else []
        )
        if not docs:
            return build_text_prompt(
                "Extract topics from knowledge base",
                get_text_prompt_v1("mcp.rag.no_documents.v1"),
            )
        summaries: list[str] = []
        tokens = 0
        for doc in docs:
            filename = doc.get("filename")
            file_type = doc.get("file_type")
            total_chunks = doc.get("total_chunks")
            source_type = doc.get("source_type")
            filename_label = filename if isinstance(filename, str) else "unknown"
            file_type_label = file_type if isinstance(file_type, str) else "unknown"
            total_chunks_label = total_chunks if isinstance(total_chunks, int) else 0
            source_label = source_type if isinstance(source_type, str) else "upload"
            line = (
                f"- {filename_label} ({file_type_label}, {total_chunks_label} chunks, "
                f"source: {source_label})"
            )
            if tokens + len(line) // 4 > 8000:
                break
            summaries.append(line)
            tokens += len(line) // 4
        top_n = _coerce_positive_int_or_raise(arguments, key="top_n", default=10)
        prompt_text = render_text_prompt_template_v1(
            "mcp.rag.topic_extraction.user_template.v1",
            {
                "RAG_DOCUMENT_COUNT": str(len(docs)),
                "RAG_DOCUMENTS": "\n".join(summaries),
                "RAG_TOP_N": str(top_n),
            },
        )
        return build_text_prompt(f"Extract top {top_n} topics from knowledge base", prompt_text)

    async def rag_question_answering(arguments: JSONDict) -> JSONDict:
        conv_id = _require_prompt_string(arguments, "conv_id")
        user_id = require_authenticated_user_id("RAG question_answering prompt")
        resolved = await rag.resolve_conv_id_for_user(conv_id, user_id)
        question = _require_prompt_string(arguments, "question")
        response = await rag.search(
            conv_id=resolved,
            query=question,
            top_k=_coerce_positive_int_or_raise(arguments, key="top_k", default=5),
            similarity_threshold=0.3,
            retrieval_strategy="similarity",
            user_id=user_id,
        )
        results_value = response.get("results")
        results = (
            [item for item in results_value if isinstance(item, dict)]
            if isinstance(results_value, list)
            else []
        )
        if not results:
            return build_text_prompt(
                f"Answer question: {question}",
                render_text_prompt_template_v1(
                    "mcp.rag.no_results.v1",
                    {"RAG_QUESTION": question},
                ),
            )
        context: list[str] = []
        tokens = 0
        for item in results:
            document_id = item.get("document_id")
            chunk_index = item.get("chunk_index")
            similarity = item.get("similarity")
            content = item.get("content")
            document_label = document_id if isinstance(document_id, str) else "unknown"
            chunk_label = chunk_index if isinstance(chunk_index, int) else "?"
            similarity_value = similarity if isinstance(similarity, int | float) else 0
            content_text = content if isinstance(content, str) else ""
            txt = (
                f"[Source: {document_label}, Chunk {chunk_label}, "
                f"Similarity: {similarity_value:.2f}]\n{content_text}"
            )
            if tokens + len(txt) // 4 > 8000:
                break
            context.append(txt)
            tokens += len(txt) // 4
        prompt_text = render_text_prompt_template_v1(
            "mcp.rag.question_answering.user_template.v1",
            {"RAG_CONTEXT": "\n".join(context), "RAG_QUESTION": question},
        )
        return build_text_prompt(f"Answer question: {question}", prompt_text)

    async def rag_compare_sources(arguments: JSONDict) -> JSONDict:
        conv_id = _require_prompt_string(arguments, "conv_id")
        user_id = require_authenticated_user_id("RAG compare_sources prompt")
        resolved = await rag.resolve_conv_id_for_user(conv_id, user_id)
        topic = _require_prompt_string(arguments, "topic")
        response = await rag.search(
            conv_id=resolved,
            query=topic,
            top_k=_coerce_positive_int_or_raise(arguments, key="top_k", default=10),
            similarity_threshold=0.5,
            retrieval_strategy="similarity",
            user_id=user_id,
        )
        results_value = response.get("results")
        results = (
            [item for item in results_value if isinstance(item, dict)]
            if isinstance(results_value, list)
            else []
        )
        if not results:
            return build_text_prompt(
                f"Compare sources on topic: {topic}",
                render_text_prompt_template_v1(
                    "mcp.rag.no_sources.v1",
                    {"RAG_TOPIC": topic},
                ),
            )
        sources: dict[str, list[str]] = {}
        tokens = 0
        for item in results:
            doc_id_value = item.get("document_id")
            doc_id = doc_id_value if isinstance(doc_id_value, str) else "unknown"
            chunk_index = item.get("chunk_index")
            chunk_label = chunk_index if isinstance(chunk_index, int) else "?"
            content = item.get("content")
            content_text = content if isinstance(content, str) else ""
            txt = f"[Chunk {chunk_label}]\n{content_text}"
            if tokens + len(txt) // 4 > 8000:
                break
            chunks = sources.get(doc_id)
            if chunks is None:
                chunks = []
                sources[doc_id] = chunks
            chunks.append(txt)
            tokens += len(txt) // 4
        sections: list[str] = []
        for doc_id, chunks in sources.items():
            sections.append(f"=== Document {doc_id} ===\n{chr(10).join(chunks)}")
        prompt_text = render_text_prompt_template_v1(
            "mcp.rag.compare_sources.user_template.v1",
            {"RAG_TOPIC": topic, "RAG_SOURCES": "\n".join(sections)},
        )
        return build_text_prompt(f"Compare sources on topic: {topic}", prompt_text)

    return {
        "rag_document_summary": rag_document_summary,
        "rag_topic_extraction": rag_topic_extraction,
        "rag_question_answering": rag_question_answering,
        "rag_compare_sources": rag_compare_sources,
    }
