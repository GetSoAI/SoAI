/* SoAI - Canonical soai_knowledge attachment content part contracts [frontend/assets/ts/features/chat/attachments/soaiKnowledgeContentPart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsValue } from '@core/time/epochMs.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNumber, isPlainObject } from '@core/typeGuards.ts';
import { hasOnlyFields, normalizeNonNegativeIntegerField, normalizeOptionalNonNegativeIntegerField, normalizeRequiredTextField, SOAI_ATTACHMENT_ID_MAX_LENGTH, SOAI_KNOWLEDGE_TITLE_MAX_LENGTH, SOAI_KNOWLEDGE_TYPE_MAX_LENGTH, type BackendMessageRecord } from '@features/chat/attachments/attachmentContentFieldValidation.ts';

type SoaiKnowledgeStoragePart = {
    type: 'soai_knowledge';
    knowledgeAttachmentId: string;
    summaryId: string;
    sourceType: string;
    operationType: string;
    title: string;
    totalCount: number;
    visibleCount: number;
    hiddenCount: number;
    statusCounts: Record<string, number>;
    attachmentRevision: number;
    firstEventId: number | null;
    lastEventId: number | null;
    createdAtMs: number;
    finalizedAtMs: number;
};

const SOAI_KNOWLEDGE_FIELDS = new Set(['type', 'knowledge_attachment_id', 'summary_id', 'source_type', 'operation_type', 'title', 'total_count', 'visible_count', 'hidden_count', 'status_counts', 'attachment_revision', 'first_event_id', 'last_event_id', 'created_at_ms', 'finalized_at_ms']);
const SOAI_KNOWLEDGE_DOMAIN_FIELDS = new Set(['type', 'knowledgeAttachmentId', 'summaryId', 'sourceType', 'operationType', 'title', 'totalCount', 'visibleCount', 'hiddenCount', 'statusCounts', 'attachmentRevision', 'firstEventId', 'lastEventId', 'createdAtMs', 'finalizedAtMs']);
const SOAI_KNOWLEDGE_SOURCE_TYPES = new Set(['composer_document_upload', 'composer_folder_upload', 'knowledge_tab_document_upload', 'knowledge_tab_folder_upload', 'file_explorer_folder_import', 'document_delete', 'bulk_delete', 'reindex', 'linked_knowledge']);
const SOAI_KNOWLEDGE_OPERATION_TYPES = new Set(['added', 'removed', 'updated', 'reindexed']);
const SOAI_KNOWLEDGE_STATUS_TYPES = new Set(['queued', 'fetching', 'parsing', 'chunking', 'embedding', 'completed', 'error', 'cancelled', 'skipped']);

const isSoaiKnowledgeSourceType = (value: string): boolean => SOAI_KNOWLEDGE_SOURCE_TYPES.has(value);

const normalizeStatusCounts = (value: JsonValue | null | undefined): Record<string, number> | null => {
    if (!isPlainObject(value)) {
        return null;
    }
    const counts: Record<string, number> = {};
    for (const [status, count] of Object.entries(value)) {
        const normalizedStatus = status.trim();
        if (!normalizedStatus || status.includes('\0') || normalizedStatus.length > SOAI_KNOWLEDGE_TYPE_MAX_LENGTH || !SOAI_KNOWLEDGE_STATUS_TYPES.has(normalizedStatus) || !isNumber(count) || !Number.isSafeInteger(count) || count < 0) {
            return null;
        }
        counts[normalizedStatus] = count;
    }
    return counts;
};

const normalizeSoaiKnowledgeStoragePart = (part: BackendMessageRecord): SoaiKnowledgeStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_KNOWLEDGE_FIELDS) || part['type'] !== 'soai_knowledge') {
        return null;
    }
    const knowledgeAttachmentId = normalizeRequiredTextField(part, 'knowledge_attachment_id', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const summaryId = normalizeRequiredTextField(part, 'summary_id', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const sourceType = normalizeRequiredTextField(part, 'source_type', SOAI_KNOWLEDGE_TYPE_MAX_LENGTH);
    const operationType = normalizeRequiredTextField(part, 'operation_type', SOAI_KNOWLEDGE_TYPE_MAX_LENGTH);
    const title = normalizeRequiredTextField(part, 'title', SOAI_KNOWLEDGE_TITLE_MAX_LENGTH);
    const totalCount = normalizeNonNegativeIntegerField(part, 'total_count');
    const visibleCount = normalizeNonNegativeIntegerField(part, 'visible_count');
    const hiddenCount = normalizeNonNegativeIntegerField(part, 'hidden_count');
    const statusCounts = normalizeStatusCounts(part['status_counts']);
    const attachmentRevision = normalizeNonNegativeIntegerField(part, 'attachment_revision');
    const firstEventId = normalizeOptionalNonNegativeIntegerField(part, 'first_event_id');
    const lastEventId = normalizeOptionalNonNegativeIntegerField(part, 'last_event_id');
    const createdAtMs = part['created_at_ms'];
    const finalizedAtMs = part['finalized_at_ms'];
    if (knowledgeAttachmentId === null || summaryId === null || sourceType === null || operationType === null || title === null || totalCount === null || visibleCount === null || hiddenCount === null || statusCounts === null || attachmentRevision === null || firstEventId === undefined || lastEventId === undefined || !isSoaiKnowledgeSourceType(sourceType) || !SOAI_KNOWLEDGE_OPERATION_TYPES.has(operationType) || !isEpochMsValue(createdAtMs) || !isEpochMsValue(finalizedAtMs)) {
        return null;
    }
    return {
        type: 'soai_knowledge',
        knowledgeAttachmentId: knowledgeAttachmentId,
        summaryId: summaryId,
        sourceType: sourceType,
        operationType: operationType,
        title,
        totalCount: totalCount,
        visibleCount: visibleCount,
        hiddenCount: hiddenCount,
        statusCounts: statusCounts,
        attachmentRevision: attachmentRevision,
        firstEventId: firstEventId,
        lastEventId: lastEventId,
        createdAtMs: createdAtMs,
        finalizedAtMs: finalizedAtMs
    };
};

const normalizeSoaiKnowledgeContentPart = (part: BackendMessageRecord): SoaiKnowledgeStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_KNOWLEDGE_DOMAIN_FIELDS) || part['type'] !== 'soai_knowledge') {
        return null;
    }
    const knowledgeAttachmentId = normalizeRequiredTextField(part, 'knowledgeAttachmentId', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const summaryId = normalizeRequiredTextField(part, 'summaryId', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const sourceType = normalizeRequiredTextField(part, 'sourceType', SOAI_KNOWLEDGE_TYPE_MAX_LENGTH);
    const operationType = normalizeRequiredTextField(part, 'operationType', SOAI_KNOWLEDGE_TYPE_MAX_LENGTH);
    const title = normalizeRequiredTextField(part, 'title', SOAI_KNOWLEDGE_TITLE_MAX_LENGTH);
    const totalCount = normalizeNonNegativeIntegerField(part, 'totalCount');
    const visibleCount = normalizeNonNegativeIntegerField(part, 'visibleCount');
    const hiddenCount = normalizeNonNegativeIntegerField(part, 'hiddenCount');
    const statusCounts = normalizeStatusCounts(part['statusCounts']);
    const attachmentRevision = normalizeNonNegativeIntegerField(part, 'attachmentRevision');
    const firstEventId = normalizeOptionalNonNegativeIntegerField(part, 'firstEventId');
    const lastEventId = normalizeOptionalNonNegativeIntegerField(part, 'lastEventId');
    const createdAtMs = part['createdAtMs'];
    const finalizedAtMs = part['finalizedAtMs'];
    if (knowledgeAttachmentId === null || summaryId === null || sourceType === null || operationType === null || title === null || totalCount === null || visibleCount === null || hiddenCount === null || statusCounts === null || attachmentRevision === null || firstEventId === undefined || lastEventId === undefined || !isSoaiKnowledgeSourceType(sourceType) || !SOAI_KNOWLEDGE_OPERATION_TYPES.has(operationType) || !isEpochMsValue(createdAtMs) || !isEpochMsValue(finalizedAtMs)) {
        return null;
    }
    return { type: 'soai_knowledge', knowledgeAttachmentId, summaryId, sourceType, operationType, title, totalCount, visibleCount, hiddenCount, statusCounts, attachmentRevision, firstEventId, lastEventId, createdAtMs, finalizedAtMs };
};

export { isSoaiKnowledgeSourceType, normalizeSoaiKnowledgeContentPart, normalizeSoaiKnowledgeStoragePart };
export type { SoaiKnowledgeStoragePart };
