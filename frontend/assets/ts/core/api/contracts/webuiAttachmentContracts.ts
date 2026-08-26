/* SoAI - Frontend WebUI attachment response contracts [frontend/assets/ts/core/api/contracts/webuiAttachmentContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeWebuiMessageContentPart, type WebuiMessageContentPart } from '@core/api/contracts/webuiMessageContentPartContract.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEpochMsValue, readRequiredTrimmedStringValue, readNullableEpochMsValue, readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PhysicalAttachmentResponse {
    clientAttachmentId: string | null;
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: string;
    providerMode: string | null;
    providerTextTruncated: boolean | null;
    parseState: string;
    parseError: string | null;
    createdAtMs: number;
    updatedAtMs: number;
    attachmentRevision: number;
    state: string;
    previewUrl: string;
    downloadUrl: string;
}
interface KnowledgeAttachmentSummary {
    knowledgeAttachmentId: string;
    summaryId: string;
    convId: string;
    userId: number;
    state: string;
    conversationInputId: string | null;
    messageCreatedAtMs: number | null;
    processingState: string;
    sourceType: string;
    operationType: string;
    title: string;
    rootLabel: string | null;
    rootVirtualPath: string | null;
    taskId: string | null;
    clientBatchId: string | null;
    firstEventId: number | null;
    lastEventId: number | null;
    stateSignature: string | null;
    totalCount: number;
    visibleCount: number;
    hiddenCount: number;
    statusCounts: Record<string, number>;
    attachmentRevision: number;
    createdAtMs: number;
    updatedAtMs: number;
    finalizedAtMs: number | null;
    expiresAtMs: number;
}
interface KnowledgeAttachmentItem {
    id: number;
    knowledgeAttachmentId: string;
    documentId: string | null;
    eventId: number | null;
    itemIndex: number;
    filename: string;
    fileType: string | null;
    fileSizeBytes: number | null;
    ragStatus: string | null;
    operationType: string;
    errorMessage: string | null;
    createdAtMs: number;
}
interface KnowledgeAttachmentCollectionResponse {
    items: KnowledgeAttachmentSummary[];
    useMaxItems: number | null;
}
interface KnowledgeAttachmentClaimResponse {
    contentParts: WebuiMessageContentPart[];
}
interface KnowledgeAttachmentClaimRequest {
    selections: Array<{ knowledgeAttachmentId: string; attachmentRevision: number }>;
}
interface KnowledgeAttachmentPreviewRequest {
    documentId: string | null;
}
interface KnowledgeAttachmentUseSelection {
    itemId: number;
    documentId: string | null;
}
interface KnowledgeAttachmentUseRequest {
    sourceConvId: string;
    sourceKnowledgeAttachmentId: string;
    selections: KnowledgeAttachmentUseSelection[];
    clientBatchId: string;
}
interface KnowledgeAttachmentItemsResponse {
    items: KnowledgeAttachmentItem[];
    count: number;
    limit: number;
    nextCursor: { itemIndex: number; id: number } | null;
    attachmentRevision: number;
}
interface KnowledgeAttachmentPreviewDocument {
    sourceConvId: string;
    sourceUserId: number;
    sourceKnowledgeAttachmentId: string;
    sourceItemId: number;
    sourceDocumentId: string;
    filename: string;
    fileType: string;
    fileSizeBytes: number;
    documentStatus: string;
    itemRagStatus: string | null;
    documentCreatedAtMs: number;
    chunkCount: number | null;
}
interface KnowledgeAttachmentPreviewResponse {
    state: 'available';
    previewType: string;
    document: KnowledgeAttachmentPreviewDocument;
    text: string | null;
}
interface KnowledgeAttachmentUseResponse {
    summary: KnowledgeAttachmentSummary;
    idempotent: boolean;
}

const requiredString = (record: JsonObject, field: string, label: string): string => readRequiredTrimmedStringValue(record[field], `${label}.${field}`);
const nullableString = (record: JsonObject, field: string, label: string): string | null => readNullableTrimmedStringValue(record[field], `${label}.${field}`);
const requiredCount = (record: JsonObject, field: string, label: string): number => readRequiredNonNegativeIntegerValue(record[field], `${label}.${field}`);
const nullableCount = (record: JsonObject, field: string, label: string): number | null => (record[field] === null || record[field] === undefined ? null : readRequiredNonNegativeIntegerValue(record[field], `${label}.${field}`));
const requiredJsonObject = (record: JsonObject, field: string, label: string): JsonObject => {
    const value = record[field];
    if (!isJsonObject(value)) throw new TypeError(`${label}.${field} must be an object.`);
    return value;
};
const decodeStatusCounts = (record: JsonObject, field: string, label: string): Record<string, number> => {
    const source = requiredJsonObject(record, field, label);
    const counts: Record<string, number> = {};
    for (const [status, value] of Object.entries(source)) counts[status] = readRequiredNonNegativeIntegerValue(value, `${label}.${field}.${status}`);
    return counts;
};

const decodePhysicalAttachment = (value: ApiResponsePayload): PhysicalAttachmentResponse => {
    const record = requireRecord(value, 'Physical attachment response');
    return {
        clientAttachmentId: nullableString(record, 'client_attachment_id', 'Physical attachment response'),
        attachmentId: requiredString(record, 'attachment_id', 'Physical attachment response'),
        fileId: requiredString(record, 'file_id', 'Physical attachment response'),
        filename: requiredString(record, 'filename', 'Physical attachment response'),
        mimeType: requiredString(record, 'mime_type', 'Physical attachment response'),
        sizeBytes: requiredCount(record, 'size_bytes', 'Physical attachment response'),
        previewType: requiredString(record, 'preview_type', 'Physical attachment response'),
        providerMode: nullableString(record, 'provider_mode', 'Physical attachment response'),
        providerTextTruncated: record['provider_text_truncated'] === null || record['provider_text_truncated'] === undefined ? null : readRequiredBooleanValue(record['provider_text_truncated'], 'Physical attachment response.provider_text_truncated'),
        parseState: requiredString(record, 'parse_state', 'Physical attachment response'),
        parseError: nullableString(record, 'parse_error', 'Physical attachment response'),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], 'Physical attachment response.created_at_ms'),
        updatedAtMs: readRequiredEpochMsValue(record['updated_at_ms'], 'Physical attachment response.updated_at_ms'),
        attachmentRevision: requiredCount(record, 'attachment_revision', 'Physical attachment response'),
        state: requiredString(record, 'state', 'Physical attachment response'),
        previewUrl: requiredString(record, 'preview_url', 'Physical attachment response'),
        downloadUrl: requiredString(record, 'download_url', 'Physical attachment response')
    };
};
const decodeKnowledgeSummary = (value: JsonValue, label = 'Knowledge attachment summary'): KnowledgeAttachmentSummary => {
    const record = requireRecord(value, label);
    return {
        knowledgeAttachmentId: requiredString(record, 'knowledge_attachment_id', label),
        summaryId: requiredString(record, 'summary_id', label),
        convId: requiredString(record, 'conv_id', label),
        userId: requiredCount(record, 'user_id', label),
        state: requiredString(record, 'state', label),
        conversationInputId: nullableString(record, 'conversation_input_id', label),
        messageCreatedAtMs: readNullableEpochMsValue(record['message_created_at_ms'], `${label}.message_created_at_ms`),
        processingState: requiredString(record, 'processing_state', label),
        sourceType: requiredString(record, 'source_type', label),
        operationType: requiredString(record, 'operation_type', label),
        title: requiredString(record, 'title', label),
        rootLabel: nullableString(record, 'root_label', label),
        rootVirtualPath: nullableString(record, 'root_virtual_path', label),
        taskId: nullableString(record, 'task_id', label),
        clientBatchId: nullableString(record, 'client_batch_id', label),
        firstEventId: nullableCount(record, 'first_event_id', label),
        lastEventId: nullableCount(record, 'last_event_id', label),
        stateSignature: nullableString(record, 'state_signature', label),
        totalCount: requiredCount(record, 'total_count', label),
        visibleCount: requiredCount(record, 'visible_count', label),
        hiddenCount: requiredCount(record, 'hidden_count', label),
        statusCounts: decodeStatusCounts(record, 'status_counts', label),
        attachmentRevision: requiredCount(record, 'attachment_revision', label),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`),
        updatedAtMs: readRequiredEpochMsValue(record['updated_at_ms'], `${label}.updated_at_ms`),
        finalizedAtMs: readNullableEpochMsValue(record['finalized_at_ms'], `${label}.finalized_at_ms`),
        expiresAtMs: readRequiredEpochMsValue(record['expires_at_ms'], `${label}.expires_at_ms`)
    };
};
const decodeSummaryCollection = (value: ApiResponsePayload): KnowledgeAttachmentCollectionResponse => {
    const record = requireRecord(value, 'Knowledge attachment collection response');
    const items = record['items'];
    if (!isJsonArray(items)) throw new TypeError('Knowledge attachment collection response.items must be an array.');
    return { items: items.map((entry, index) => decodeKnowledgeSummary(entry, `Knowledge attachment collection response.items[${String(index)}]`)), useMaxItems: record['use_max_items'] === undefined ? null : requiredCount(record, 'use_max_items', 'Knowledge attachment collection response') };
};
const decodeClaim = (value: ApiResponsePayload): KnowledgeAttachmentClaimResponse => {
    const record = requireRecord(value, 'Knowledge attachment claim response');
    const parts = record['content_parts'];
    if (!isJsonArray(parts)) throw new TypeError('Knowledge attachment claim response.content_parts must be an array.');
    return { contentParts: parts.map((part, index) => decodeWebuiMessageContentPart(part, `Knowledge attachment claim response.content_parts[${String(index)}]`)) };
};
const decodeItem = (value: JsonValue, label: string): KnowledgeAttachmentItem => {
    const record = requireRecord(value, label);
    return { id: requiredCount(record, 'id', label), knowledgeAttachmentId: requiredString(record, 'knowledge_attachment_id', label), documentId: nullableString(record, 'document_id', label), eventId: nullableCount(record, 'event_id', label), itemIndex: requiredCount(record, 'item_index', label), filename: requiredString(record, 'filename', label), fileType: nullableString(record, 'file_type', label), fileSizeBytes: nullableCount(record, 'file_size_bytes', label), ragStatus: nullableString(record, 'rag_status', label), operationType: requiredString(record, 'operation_type', label), errorMessage: nullableString(record, 'error_message', label), createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`) };
};
const decodePreview = (value: ApiResponsePayload): KnowledgeAttachmentPreviewResponse => {
    const record = requireRecord(value, 'Knowledge attachment preview response');
    const document = requireRecord(record['document'], 'Knowledge attachment preview response.document');
    return {
        state: 'available',
        previewType: requiredString(record, 'preview_type', 'Knowledge attachment preview response'),
        document: {
            sourceConvId: requiredString(document, 'source_conv_id', 'Knowledge attachment preview document'),
            sourceUserId: requiredCount(document, 'source_user_id', 'Knowledge attachment preview document'),
            sourceKnowledgeAttachmentId: requiredString(document, 'source_knowledge_attachment_id', 'Knowledge attachment preview document'),
            sourceItemId: requiredCount(document, 'source_item_id', 'Knowledge attachment preview document'),
            sourceDocumentId: requiredString(document, 'source_document_id', 'Knowledge attachment preview document'),
            filename: requiredString(document, 'filename', 'Knowledge attachment preview document'),
            fileType: requiredString(document, 'file_type', 'Knowledge attachment preview document'),
            fileSizeBytes: requiredCount(document, 'file_size_bytes', 'Knowledge attachment preview document'),
            documentStatus: requiredString(document, 'document_status', 'Knowledge attachment preview document'),
            itemRagStatus: nullableString(document, 'item_rag_status', 'Knowledge attachment preview document'),
            documentCreatedAtMs: readRequiredEpochMsValue(document['document_created_at_ms'], 'Knowledge attachment preview document.document_created_at_ms'),
            chunkCount: nullableCount(document, 'chunk_count', 'Knowledge attachment preview document')
        },
        text: record['text'] === null || record['text'] === undefined ? null : readRequiredTrimmedStringValue(record['text'], 'Knowledge attachment preview response.text')
    };
};
const decodeItems = (value: ApiResponsePayload): KnowledgeAttachmentItemsResponse => {
    const record = requireRecord(value, 'Knowledge attachment items response');
    const items = record['items'];
    if (!isJsonArray(items)) throw new TypeError('Knowledge attachment items response.items must be an array.');
    const cursorValue = record['next_cursor'];
    let nextCursor: KnowledgeAttachmentItemsResponse['nextCursor'] = null;
    if (cursorValue !== null && cursorValue !== undefined) {
        const cursor = requireRecord(cursorValue, 'Knowledge attachment items response.next_cursor');
        nextCursor = { itemIndex: requiredCount(cursor, 'item_index', 'Knowledge attachment items response.next_cursor'), id: requiredCount(cursor, 'id', 'Knowledge attachment items response.next_cursor') };
    }
    return { items: items.map((item, index) => decodeItem(item, `Knowledge attachment items response.items[${String(index)}]`)), count: requiredCount(record, 'count', 'Knowledge attachment items response'), limit: requiredCount(record, 'limit', 'Knowledge attachment items response'), nextCursor: nextCursor, attachmentRevision: requiredCount(record, 'attachment_revision', 'Knowledge attachment items response') };
};
const decodeSummary = (value: ApiResponsePayload): KnowledgeAttachmentSummary => decodeKnowledgeSummary(requireRecord(value, 'Knowledge attachment summary'));
const decodeKnowledgeAttachmentChangedEvent = (value: JsonValue): KnowledgeAttachmentSummary => {
    const label = 'Knowledge attachment changed event';
    const record = requireRecord(value, label);
    const summary = decodeKnowledgeSummary(requireRecord(record['summary'], `${label}.summary`), `${label}.summary`);
    const envelope = {
        userId: requiredCount(record, 'user_id', label),
        convId: requiredString(record, 'conv_id', label),
        knowledgeAttachmentId: requiredString(record, 'knowledge_attachment_id', label),
        taskId: nullableString(record, 'task_id', label),
        processingState: requiredString(record, 'processing_state', label),
        state: requiredString(record, 'state', label),
        attachmentRevision: requiredCount(record, 'attachment_revision', label),
        updatedAtMs: readRequiredEpochMsValue(record['updated_at_ms'], `${label}.updated_at_ms`)
    };
    const matchingFields = envelope.userId === summary.userId && envelope.convId === summary.convId && envelope.knowledgeAttachmentId === summary.knowledgeAttachmentId && envelope.taskId === summary.taskId && envelope.processingState === summary.processingState && envelope.state === summary.state && envelope.attachmentRevision === summary.attachmentRevision && envelope.updatedAtMs === summary.updatedAtMs;
    if (!matchingFields) throw new TypeError(`${label} envelope does not match summary fields: user_id, conv_id, knowledge_attachment_id, task_id, processing_state, state, attachment_revision, updated_at_ms.`);
    return summary;
};
const decodeUse = (value: ApiResponsePayload): KnowledgeAttachmentUseResponse => {
    const record = requireRecord(value, 'Knowledge attachment use response');
    return { summary: decodeKnowledgeSummary(requireRecord(record['summary'], 'Knowledge attachment use response.summary'), 'Knowledge attachment use response.summary'), idempotent: readRequiredBooleanValue(record['idempotent'], 'Knowledge attachment use response.idempotent') };
};

export { decodeClaim, decodeItems, decodeKnowledgeAttachmentChangedEvent, decodePhysicalAttachment, decodePreview, decodeSummary, decodeSummaryCollection, decodeUse };
export type { KnowledgeAttachmentClaimRequest, KnowledgeAttachmentClaimResponse, KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentItem, KnowledgeAttachmentItemsResponse, KnowledgeAttachmentPreviewDocument, KnowledgeAttachmentPreviewRequest, KnowledgeAttachmentPreviewResponse, KnowledgeAttachmentSummary, KnowledgeAttachmentUseRequest, KnowledgeAttachmentUseResponse, KnowledgeAttachmentUseSelection, PhysicalAttachmentResponse };
