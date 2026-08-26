/* SoAI - Frontend WebUI RAG response contracts [frontend/assets/ts/core/api/contracts/webuiRagContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeSummary, type KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredEpochMsValue, readRequiredTrimmedStringValue, readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface RagConfigResponse {
    convId: string;
    enabled: boolean;
    retrievalStrategy: string;
    topK: number;
    similarityThreshold: number;
    chunkingStrategy: string;
    chunkSize: number;
    chunkOverlap: number;
    embeddingModel: string | null;
    defaultEmbeddingModel: string | null;
}
interface RagConfigUpdateRequest {
    enabled?: boolean | null;
    retrievalStrategy?: string | null;
    topK?: number | null;
    similarityThreshold?: number | null;
    chunkingStrategy?: string | null;
    chunkSize?: number | null;
    chunkOverlap?: number | null;
    embeddingModel?: string | null;
}
interface RagDocumentResponse {
    id: string;
    filename: string;
    fileSizeBytes: number | null;
    status: string;
    statusDetails: string | null;
    totalChunks: number | null;
    processedChunks: number | null;
    createdAtMs: number | null;
    errorMessage: string | null;
}
interface RagDocumentStatusCounts {
    queued: number;
    fetching: number;
    parsing: number;
    chunking: number;
    embedding: number;
    completed: number;
    error: number;
}
interface RagDocumentsResponse {
    convId: string;
    documents: RagDocumentResponse[];
    count: number;
    chunkCount: number;
    statusCounts: RagDocumentStatusCounts;
    limit: number;
    offset: number;
}
interface RagBatchResultResponse {
    index: number;
    status: 'queued' | 'rate_limited' | 'failed';
    error?: string | undefined;
    retryAfterSeconds?: number | undefined;
}
interface RagBatchUploadResponse {
    status: 'accepted';
    convId: string;
    queued: number;
    rateLimited: number;
    failed: number;
    total: number;
    results?: RagBatchResultResponse[] | undefined;
    knowledgeAttachment?: KnowledgeAttachmentSummary | undefined;
}
interface RagUploadResponse {
    taskId: string;
    knowledgeAttachment: KnowledgeAttachmentSummary | null;
    documentId?: string | undefined;
    filename?: string | undefined;
    status?: string | undefined;
}
interface RagIngestResponse {
    status: 'accepted' | 'queued';
    taskId: string;
    knowledgeAttachmentId: string;
    knowledgeAttachment: KnowledgeAttachmentSummary;
}
interface RagDeleteResponse {
    status: string;
    knowledgeAttachment?: KnowledgeAttachmentSummary | undefined;
}
interface RagReindexResponse {
    status: 'queued';
    taskId: string;
    convId: string;
    embeddingModel: string;
    knowledgeAttachment: KnowledgeAttachmentSummary;
}

const requiredString = (record: JsonObject, field: string, label: string): string => readRequiredTrimmedStringValue(record[field], `${label}.${field}`);
const nullableString = (record: JsonObject, field: string, label: string): string | null => readNullableTrimmedStringValue(record[field], `${label}.${field}`);
const count = (record: JsonObject, field: string, label: string): number => readRequiredNonNegativeIntegerValue(record[field], `${label}.${field}`);
const nullableCount = (record: JsonObject, field: string, label: string): number | null => (record[field] === null || record[field] === undefined ? null : readRequiredNonNegativeIntegerValue(record[field], `${label}.${field}`));
const object = (value: JsonValue | undefined, label: string): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object.`);
    return value;
};

const decodeRagConfig = (value: ApiResponsePayload): RagConfigResponse => {
    const record = requireRecord(value, 'RAG config response');
    return { convId: requiredString(record, 'conv_id', 'RAG config response'), enabled: readRequiredBooleanValue(record['enabled'], 'RAG config response.enabled'), retrievalStrategy: requiredString(record, 'retrieval_strategy', 'RAG config response'), topK: readRequiredFiniteNumberValue(record['top_k'], 'RAG config response.top_k'), similarityThreshold: readRequiredFiniteNumberValue(record['similarity_threshold'], 'RAG config response.similarity_threshold'), chunkingStrategy: requiredString(record, 'chunking_strategy', 'RAG config response'), chunkSize: readRequiredFiniteNumberValue(record['chunk_size'], 'RAG config response.chunk_size'), chunkOverlap: readRequiredFiniteNumberValue(record['chunk_overlap'], 'RAG config response.chunk_overlap'), embeddingModel: nullableString(record, 'embedding_model', 'RAG config response'), defaultEmbeddingModel: nullableString(record, 'default_embedding_model', 'RAG config response') };
};

const serializeRagConfigUpdateRequest = (request: RagConfigUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.enabled !== undefined) serialized['enabled'] = request.enabled;
    if (request.retrievalStrategy !== undefined) serialized['retrieval_strategy'] = request.retrievalStrategy;
    if (request.topK !== undefined) serialized['top_k'] = request.topK;
    if (request.similarityThreshold !== undefined) serialized['similarity_threshold'] = request.similarityThreshold;
    if (request.chunkingStrategy !== undefined) serialized['chunking_strategy'] = request.chunkingStrategy;
    if (request.chunkSize !== undefined) serialized['chunk_size'] = request.chunkSize;
    if (request.chunkOverlap !== undefined) serialized['chunk_overlap'] = request.chunkOverlap;
    if (request.embeddingModel !== undefined) serialized['embedding_model'] = request.embeddingModel;
    return serialized;
};
const decodeRagDocument = (value: JsonValue, label: string): RagDocumentResponse => {
    const record = requireRecord(value, label);
    return { id: requiredString(record, 'id', label), filename: requiredString(record, 'filename', label), fileSizeBytes: nullableCount(record, 'file_size_bytes', label), status: requiredString(record, 'status', label), statusDetails: nullableString(record, 'status_details', label), totalChunks: nullableCount(record, 'total_chunks', label), processedChunks: nullableCount(record, 'processed_chunks', label), createdAtMs: record['created_at_ms'] === null || record['created_at_ms'] === undefined ? null : readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`), errorMessage: nullableString(record, 'error_message', label) };
};
const decodeRagDocuments = (value: ApiResponsePayload): RagDocumentsResponse => {
    const record = requireRecord(value, 'RAG documents response');
    const documents = record['documents'];
    const normalizedDocuments = documents === undefined ? [] : documents;
    if (!isJsonArray(normalizedDocuments)) throw new TypeError('RAG documents response.documents must be an array.');
    const statusCountsRecord = object(record['status_counts'], 'RAG documents response.status_counts');
    const statusCounts = {
        queued: count(statusCountsRecord, 'queued', 'RAG documents response.status_counts'),
        fetching: count(statusCountsRecord, 'fetching', 'RAG documents response.status_counts'),
        parsing: count(statusCountsRecord, 'parsing', 'RAG documents response.status_counts'),
        chunking: count(statusCountsRecord, 'chunking', 'RAG documents response.status_counts'),
        embedding: count(statusCountsRecord, 'embedding', 'RAG documents response.status_counts'),
        completed: count(statusCountsRecord, 'completed', 'RAG documents response.status_counts'),
        error: count(statusCountsRecord, 'error', 'RAG documents response.status_counts')
    };
    return { convId: requiredString(record, 'conv_id', 'RAG documents response'), documents: normalizedDocuments.map((entry, index) => decodeRagDocument(entry, `RAG documents response.documents[${String(index)}]`)), count: count(record, 'count', 'RAG documents response'), chunkCount: count(record, 'chunk_count', 'RAG documents response'), statusCounts, limit: count(record, 'limit', 'RAG documents response'), offset: count(record, 'offset', 'RAG documents response') };
};
const decodeRagBatch = (value: ApiResponsePayload): RagBatchUploadResponse => {
    const record = requireRecord(value, 'RAG batch upload response');
    const resultsValue = record['results'];
    let results: RagBatchResultResponse[] | undefined;
    if (resultsValue !== undefined) {
        if (!isJsonArray(resultsValue)) throw new TypeError('RAG batch upload response.results must be an array.');
        results = resultsValue.map((entry, index) => {
            const item = requireRecord(entry, `RAG batch upload response.results[${String(index)}]`);
            const status = readRequiredEnumValue(item['status'], `RAG batch upload response.results[${String(index)}].status`, ['queued', 'rate_limited', 'failed']);
            const result: RagBatchResultResponse = { index: count(item, 'index', 'RAG batch upload response result'), status };
            if (typeof item['error'] === 'string') result.error = item['error'];
            if (typeof item['retry_after_seconds'] === 'number') result.retryAfterSeconds = item['retry_after_seconds'];
            return result;
        });
    }
    return { status: readRequiredEnumValue(record['status'], 'RAG batch upload response.status', ['accepted']), convId: requiredString(record, 'conv_id', 'RAG batch upload response'), queued: count(record, 'queued', 'RAG batch upload response'), rateLimited: count(record, 'rate_limited', 'RAG batch upload response'), failed: count(record, 'failed', 'RAG batch upload response'), total: count(record, 'total', 'RAG batch upload response'), results, knowledgeAttachment: record['knowledge_attachment'] === undefined ? undefined : decodeSummary(record['knowledge_attachment']) };
};
const decodeRagUpload = (value: ApiResponsePayload): RagUploadResponse => {
    const record = requireRecord(value, 'RAG upload response');
    return { taskId: requiredString(record, 'task_id', 'RAG upload response'), knowledgeAttachment: record['knowledge_attachment'] === null || record['knowledge_attachment'] === undefined ? null : decodeSummary(record['knowledge_attachment']), documentId: typeof record['document_id'] === 'string' ? record['document_id'] : undefined, filename: typeof record['filename'] === 'string' ? record['filename'] : undefined, status: typeof record['status'] === 'string' ? record['status'] : undefined };
};
const decodeRagIngest = (value: ApiResponsePayload): RagIngestResponse => {
    const record = requireRecord(value, 'RAG file explorer ingest response');
    return { status: readRequiredEnumValue(record['status'], 'RAG file explorer ingest response.status', ['accepted', 'queued']), taskId: requiredString(record, 'task_id', 'RAG file explorer ingest response'), knowledgeAttachmentId: requiredString(record, 'knowledge_attachment_id', 'RAG file explorer ingest response'), knowledgeAttachment: decodeSummary(record['knowledge_attachment']) };
};
const decodeRagDelete = (value: ApiResponsePayload): RagDeleteResponse => {
    const record = requireRecord(value, 'RAG delete response');
    return { status: requiredString(record, 'status', 'RAG delete response'), knowledgeAttachment: record['knowledge_attachment'] === undefined ? undefined : decodeSummary(record['knowledge_attachment']) };
};
const decodeRagReindex = (value: ApiResponsePayload): RagReindexResponse => {
    const record = requireRecord(value, 'RAG reindex response');
    return { status: readRequiredEnumValue(record['status'], 'RAG reindex response.status', ['queued']), taskId: requiredString(record, 'task_id', 'RAG reindex response'), convId: requiredString(record, 'conv_id', 'RAG reindex response'), embeddingModel: requiredString(record, 'embedding_model', 'RAG reindex response'), knowledgeAttachment: decodeSummary(record['knowledge_attachment']) };
};

export { decodeRagBatch, decodeRagConfig, decodeRagDelete, decodeRagDocuments, decodeRagIngest, decodeRagReindex, decodeRagUpload, serializeRagConfigUpdateRequest };
export type { RagBatchResultResponse, RagBatchUploadResponse, RagConfigResponse, RagConfigUpdateRequest, RagDeleteResponse, RagDocumentResponse, RagDocumentStatusCounts, RagDocumentsResponse, RagIngestResponse, RagReindexResponse, RagUploadResponse };
