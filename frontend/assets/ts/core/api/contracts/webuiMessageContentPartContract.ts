/* SoAI - WebUI message content-part boundary contract [frontend/assets/ts/core/api/contracts/webuiMessageContentPartContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiPathContentPart } from '@core/api/contracts/webuiChatOperationContractTypes.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredEnumValue, readRequiredEpochMsValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface WebuiTextContentPart {
    type: 'text';
    text: string;
}
interface WebuiImageContentPart {
    type: 'image_url';
    imageUrl: { url: string; detail?: string | undefined };
    title?: string | undefined;
    alt?: string | undefined;
}
interface WebuiInputAudioContentPart {
    type: 'input_audio';
    inputAudio: JsonObject;
}
interface WebuiFileContentPart {
    type: 'file';
    file: JsonObject;
}
interface WebuiRefusalContentPart {
    type: 'refusal';
    refusal: string;
}
type WebuiSoaiPathContentPart = SoaiPathContentPart;
interface WebuiSoaiFileContentPart {
    type: 'soai_file';
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: string;
    attachmentRevision: number;
    createdAtMs: number;
}
interface WebuiSoaiKnowledgeContentPart {
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
}
const SOURCE_ATTACHMENT_UNAVAILABLE_REASON = 'source_attachment_unavailable';
interface WebuiSoaiFileUnavailableContentPart {
    type: 'soai_file_unavailable';
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: string;
    reason: typeof SOURCE_ATTACHMENT_UNAVAILABLE_REASON;
}
interface WebuiSoaiKnowledgeUnavailableContentPart {
    type: 'soai_knowledge_unavailable';
    title: string;
    sourceType: string;
    reason: typeof SOURCE_ATTACHMENT_UNAVAILABLE_REASON;
}

type WebuiMessageContentPart = WebuiTextContentPart | WebuiImageContentPart | WebuiInputAudioContentPart | WebuiFileContentPart | WebuiRefusalContentPart | WebuiSoaiPathContentPart | WebuiSoaiFileContentPart | WebuiSoaiKnowledgeContentPart | WebuiSoaiFileUnavailableContentPart | WebuiSoaiKnowledgeUnavailableContentPart;
type WebuiMessageContent = string | WebuiMessageContentPart[] | null;

const requireOnlyFields = (record: JsonObject, fields: ReadonlySet<string>, label: string): void => {
    if (Object.keys(record).some((field) => !fields.has(field))) throw new TypeError(`${label} contains unsupported fields.`);
};

const SOAI_FILE_UNAVAILABLE_FIELDS = new Set(['type', 'filename', 'mime_type', 'size_bytes', 'preview_type', 'reason']);
const SOAI_KNOWLEDGE_UNAVAILABLE_FIELDS = new Set(['type', 'title', 'source_type', 'reason']);

const decodeStatusCounts = (value: JsonValue | undefined, label: string): Record<string, number> => {
    const record = requireRecord(value, label);
    const counts: Record<string, number> = {};
    for (const [key, entry] of Object.entries(record)) counts[key] = readRequiredNonNegativeIntegerValue(entry, `${label}.${key}`);
    return counts;
};

const decodeWebuiMessageContentPart = (value: JsonValue, label: string): WebuiMessageContentPart => {
    const record = requireRecord(value, label);
    const type = readRequiredTrimmedStringValue(record['type'], `${label}.type`);
    if (type === 'text') return { type, text: readRequiredStringValue(record['text'], `${label}.text`) };
    if (type === 'refusal') return { type, refusal: readRequiredStringValue(record['refusal'], `${label}.refusal`) };
    if (type === 'image_url') {
        const image = requireRecord(record['image_url'], `${label}.image_url`);
        return { type, imageUrl: { url: readRequiredTrimmedStringValue(image['url'], `${label}.image_url.url`), detail: typeof image['detail'] === 'string' ? image['detail'] : undefined }, title: typeof record['title'] === 'string' ? record['title'] : undefined, alt: typeof record['alt'] === 'string' ? record['alt'] : undefined };
    }
    if (type === 'input_audio') return { type, inputAudio: requireRecord(record['input_audio'], `${label}.input_audio`) };
    if (type === 'file') return { type, file: requireRecord(record['file'], `${label}.file`) };
    if (type === 'soai_path') {
        const sourceReference = requireRecord(record['source_reference'], `${label}.source_reference`);
        const toolReference = requireRecord(record['tool_reference'], `${label}.tool_reference`);
        const workspaceScope = requireRecord(record['workspace_scope'], `${label}.workspace_scope`);
        const targetFingerprint = requireRecord(record['target_fingerprint'], `${label}.target_fingerprint`);
        return {
            type,
            entryType: readRequiredEnumValue(record['entry_type'], `${label}.entry_type`, ['file', 'folder']),
            sourceReference: { type: readRequiredEnumValue(sourceReference['type'], `${label}.source_reference.type`, ['conversation_virtual_path']), value: readRequiredTrimmedStringValue(sourceReference['value'], `${label}.source_reference.value`) },
            toolReference: { type: readRequiredEnumValue(toolReference['type'], `${label}.tool_reference.type`, ['workspace_relative_path']), value: readRequiredTrimmedStringValue(toolReference['value'], `${label}.tool_reference.value`) },
            workspaceScope: { type: readRequiredEnumValue(workspaceScope['type'], `${label}.workspace_scope.type`, ['conversation_effective_workspace']), rootFingerprint: readRequiredTrimmedStringValue(workspaceScope['root_fingerprint'], `${label}.workspace_scope.root_fingerprint`) },
            targetFingerprint: { type: readRequiredEnumValue(targetFingerprint['type'], `${label}.target_fingerprint.type`, ['file_sha256', 'folder_listing_sha256']), value: readRequiredTrimmedStringValue(targetFingerprint['value'], `${label}.target_fingerprint.value`) },
            title: readRequiredTrimmedStringValue(record['title'], `${label}.title`),
            previewType: readRequiredTrimmedStringValue(record['preview_type'], `${label}.preview_type`),
            mimeType: typeof record['mime_type'] === 'string' ? record['mime_type'] : null,
            sizeBytes: typeof record['size_bytes'] === 'number' ? record['size_bytes'] : null,
            modifiedAtMs: readRequiredEpochMsValue(record['modified_at_ms'], `${label}.modified_at_ms`),
            resolvedAtMs: readRequiredEpochMsValue(record['resolved_at_ms'], `${label}.resolved_at_ms`)
        };
    }
    if (type === 'soai_file') return { type, attachmentId: readRequiredTrimmedStringValue(record['attachment_id'], `${label}.attachment_id`), fileId: readRequiredTrimmedStringValue(record['file_id'], `${label}.file_id`), filename: readRequiredTrimmedStringValue(record['filename'], `${label}.filename`), mimeType: readRequiredTrimmedStringValue(record['mime_type'], `${label}.mime_type`), sizeBytes: readRequiredNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`), previewType: readRequiredTrimmedStringValue(record['preview_type'], `${label}.preview_type`), attachmentRevision: readRequiredNonNegativeIntegerValue(record['attachment_revision'], `${label}.attachment_revision`), createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`) };
    if (type === 'soai_file_unavailable') {
        requireOnlyFields(record, SOAI_FILE_UNAVAILABLE_FIELDS, label);
        return { type, filename: readRequiredTrimmedStringValue(record['filename'], `${label}.filename`), mimeType: readRequiredTrimmedStringValue(record['mime_type'], `${label}.mime_type`), sizeBytes: readRequiredNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`), previewType: readRequiredTrimmedStringValue(record['preview_type'], `${label}.preview_type`), reason: readRequiredEnumValue(record['reason'], `${label}.reason`, [SOURCE_ATTACHMENT_UNAVAILABLE_REASON]) };
    }
    if (type === 'soai_knowledge_unavailable') {
        requireOnlyFields(record, SOAI_KNOWLEDGE_UNAVAILABLE_FIELDS, label);
        return { type, title: readRequiredTrimmedStringValue(record['title'], `${label}.title`), sourceType: readRequiredTrimmedStringValue(record['source_type'], `${label}.source_type`), reason: readRequiredEnumValue(record['reason'], `${label}.reason`, [SOURCE_ATTACHMENT_UNAVAILABLE_REASON]) };
    }
    if (type === 'soai_knowledge')
        return {
            type,
            knowledgeAttachmentId: readRequiredTrimmedStringValue(record['knowledge_attachment_id'], `${label}.knowledge_attachment_id`),
            summaryId: readRequiredTrimmedStringValue(record['summary_id'], `${label}.summary_id`),
            sourceType: readRequiredTrimmedStringValue(record['source_type'], `${label}.source_type`),
            operationType: readRequiredTrimmedStringValue(record['operation_type'], `${label}.operation_type`),
            title: readRequiredTrimmedStringValue(record['title'], `${label}.title`),
            totalCount: readRequiredNonNegativeIntegerValue(record['total_count'], `${label}.total_count`),
            visibleCount: readRequiredNonNegativeIntegerValue(record['visible_count'], `${label}.visible_count`),
            hiddenCount: readRequiredNonNegativeIntegerValue(record['hidden_count'], `${label}.hidden_count`),
            statusCounts: decodeStatusCounts(record['status_counts'], `${label}.status_counts`),
            attachmentRevision: readRequiredNonNegativeIntegerValue(record['attachment_revision'], `${label}.attachment_revision`),
            firstEventId: typeof record['first_event_id'] === 'number' ? record['first_event_id'] : null,
            lastEventId: typeof record['last_event_id'] === 'number' ? record['last_event_id'] : null,
            createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`),
            finalizedAtMs: readRequiredEpochMsValue(record['finalized_at_ms'], `${label}.finalized_at_ms`)
        };
    throw new TypeError(`${label}.type is unsupported.`);
};

export { decodeWebuiMessageContentPart, SOURCE_ATTACHMENT_UNAVAILABLE_REASON };
export type { WebuiFileContentPart, WebuiImageContentPart, WebuiInputAudioContentPart, WebuiMessageContent, WebuiMessageContentPart, WebuiRefusalContentPart, WebuiSoaiFileContentPart, WebuiSoaiFileUnavailableContentPart, WebuiSoaiKnowledgeContentPart, WebuiSoaiKnowledgeUnavailableContentPart, WebuiSoaiPathContentPart, WebuiTextContentPart };
