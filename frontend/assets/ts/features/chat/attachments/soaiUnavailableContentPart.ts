/* SoAI - Canonical unavailable attachment snapshot contracts [frontend/assets/ts/features/chat/attachments/soaiUnavailableContentPart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { SOURCE_ATTACHMENT_UNAVAILABLE_REASON } from '@core/api/contracts/webuiMessageContentPartContract.ts';
import { hasOnlyFields, normalizeNonNegativeIntegerField, normalizeRequiredTextField, SOAI_FILE_MIME_TYPE_MAX_LENGTH, SOAI_FILE_NAME_MAX_LENGTH, SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH, SOAI_KNOWLEDGE_TITLE_MAX_LENGTH, SOAI_KNOWLEDGE_TYPE_MAX_LENGTH, type BackendMessageRecord } from '@features/chat/attachments/attachmentContentFieldValidation.ts';
import { isSoaiFilePreviewType, type SoaiFilePreviewType } from '@features/chat/attachments/attachmentPreviewTypes.ts';
import { isSoaiKnowledgeSourceType } from '@features/chat/attachments/soaiKnowledgeContentPart.ts';

type SoaiUnavailableReason = typeof SOURCE_ATTACHMENT_UNAVAILABLE_REASON;

type SoaiFileUnavailablePart = {
    type: 'soai_file_unavailable';
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: SoaiFilePreviewType;
    reason: SoaiUnavailableReason;
};

type SoaiKnowledgeUnavailablePart = {
    type: 'soai_knowledge_unavailable';
    title: string;
    sourceType: string;
    reason: SoaiUnavailableReason;
};

const FILE_DOMAIN_FIELDS = new Set(['type', 'filename', 'mimeType', 'sizeBytes', 'previewType', 'reason']);
const FILE_STORAGE_FIELDS = new Set(['type', 'filename', 'mime_type', 'size_bytes', 'preview_type', 'reason']);
const KNOWLEDGE_DOMAIN_FIELDS = new Set(['type', 'title', 'sourceType', 'reason']);
const KNOWLEDGE_STORAGE_FIELDS = new Set(['type', 'title', 'source_type', 'reason']);

const normalizeFile = (part: BackendMessageRecord, storage: boolean): SoaiFileUnavailablePart | null => {
    const fields = storage ? FILE_STORAGE_FIELDS : FILE_DOMAIN_FIELDS;
    if (!hasOnlyFields(part, fields) || part['type'] !== 'soai_file_unavailable' || part['reason'] !== SOURCE_ATTACHMENT_UNAVAILABLE_REASON) return null;
    const filename = normalizeRequiredTextField(part, 'filename', SOAI_FILE_NAME_MAX_LENGTH);
    const mimeType = normalizeRequiredTextField(part, storage ? 'mime_type' : 'mimeType', SOAI_FILE_MIME_TYPE_MAX_LENGTH);
    const sizeBytes = normalizeNonNegativeIntegerField(part, storage ? 'size_bytes' : 'sizeBytes');
    const previewType = normalizeRequiredTextField(part, storage ? 'preview_type' : 'previewType', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    if (filename === null || mimeType === null || sizeBytes === null || previewType === null || !isSoaiFilePreviewType(previewType)) return null;
    return { type: 'soai_file_unavailable', filename, mimeType, sizeBytes, previewType, reason: SOURCE_ATTACHMENT_UNAVAILABLE_REASON };
};

const normalizeKnowledge = (part: BackendMessageRecord, storage: boolean): SoaiKnowledgeUnavailablePart | null => {
    const fields = storage ? KNOWLEDGE_STORAGE_FIELDS : KNOWLEDGE_DOMAIN_FIELDS;
    if (!hasOnlyFields(part, fields) || part['type'] !== 'soai_knowledge_unavailable' || part['reason'] !== SOURCE_ATTACHMENT_UNAVAILABLE_REASON) return null;
    const title = normalizeRequiredTextField(part, 'title', SOAI_KNOWLEDGE_TITLE_MAX_LENGTH);
    const sourceType = normalizeRequiredTextField(part, storage ? 'source_type' : 'sourceType', SOAI_KNOWLEDGE_TYPE_MAX_LENGTH);
    if (title === null || sourceType === null || !isSoaiKnowledgeSourceType(sourceType)) return null;
    return { type: 'soai_knowledge_unavailable', title, sourceType, reason: SOURCE_ATTACHMENT_UNAVAILABLE_REASON };
};

const normalizeSoaiUnavailableFileContentPart = (part: BackendMessageRecord): SoaiFileUnavailablePart | null => normalizeFile(part, false);
const normalizeSoaiUnavailableFileStoragePart = (part: BackendMessageRecord): SoaiFileUnavailablePart | null => normalizeFile(part, true);
const normalizeSoaiUnavailableKnowledgeContentPart = (part: BackendMessageRecord): SoaiKnowledgeUnavailablePart | null => normalizeKnowledge(part, false);
const normalizeSoaiUnavailableKnowledgeStoragePart = (part: BackendMessageRecord): SoaiKnowledgeUnavailablePart | null => normalizeKnowledge(part, true);

const serializeSoaiUnavailableContentPart = (part: SoaiFileUnavailablePart | SoaiKnowledgeUnavailablePart): JsonObject => {
    if (part.type === 'soai_file_unavailable') return { type: part.type, filename: part.filename, 'mime_type': part.mimeType, 'size_bytes': part.sizeBytes, 'preview_type': part.previewType, reason: part.reason };
    return { type: part.type, title: part.title, 'source_type': part.sourceType, reason: part.reason };
};

export { normalizeSoaiUnavailableFileContentPart, normalizeSoaiUnavailableFileStoragePart, normalizeSoaiUnavailableKnowledgeContentPart, normalizeSoaiUnavailableKnowledgeStoragePart, serializeSoaiUnavailableContentPart };
export type { SoaiFileUnavailablePart, SoaiKnowledgeUnavailablePart, SoaiUnavailableReason };
