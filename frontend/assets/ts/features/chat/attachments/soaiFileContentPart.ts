/* SoAI - Canonical soai_file attachment content part contracts [frontend/assets/ts/features/chat/attachments/soaiFileContentPart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsValue } from '@core/time/epochMs.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { hasOnlyFields, normalizeNonNegativeIntegerField, normalizeRequiredTextField, SOAI_ATTACHMENT_ID_MAX_LENGTH, SOAI_FILE_MIME_TYPE_MAX_LENGTH, SOAI_FILE_NAME_MAX_LENGTH, SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH, type BackendMessageRecord } from '@features/chat/attachments/attachmentContentFieldValidation.ts';
import { isSoaiFilePreviewType, type SoaiFilePreviewType } from '@features/chat/attachments/attachmentPreviewTypes.ts';

type SoaiFileContentPartFields = {
    type: 'soai_file';
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: string;
    attachmentRevision: number;
    createdAtMs: number;
};

type SoaiFileStoragePart = JsonObject & SoaiFileContentPartFields & { previewType: SoaiFilePreviewType };

const SOAI_FILE_FIELDS = new Set(['type', 'attachment_id', 'file_id', 'filename', 'mime_type', 'size_bytes', 'preview_type', 'attachment_revision', 'created_at_ms']);
const SOAI_FILE_DOMAIN_FIELDS = new Set(['type', 'attachmentId', 'fileId', 'filename', 'mimeType', 'sizeBytes', 'previewType', 'attachmentRevision', 'createdAtMs']);

const normalizeSoaiFileContentPart = (part: BackendMessageRecord): SoaiFileStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_FILE_DOMAIN_FIELDS) || part['type'] !== 'soai_file') {
        return null;
    }
    const attachmentId = normalizeRequiredTextField(part, 'attachmentId', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const fileId = normalizeRequiredTextField(part, 'fileId', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const filename = normalizeRequiredTextField(part, 'filename', SOAI_FILE_NAME_MAX_LENGTH);
    const mimeType = normalizeRequiredTextField(part, 'mimeType', SOAI_FILE_MIME_TYPE_MAX_LENGTH);
    const sizeBytes = normalizeNonNegativeIntegerField(part, 'sizeBytes');
    const previewType = normalizeRequiredTextField(part, 'previewType', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const attachmentRevision = normalizeNonNegativeIntegerField(part, 'attachmentRevision');
    const createdAtMs = part['createdAtMs'];
    if (attachmentId === null || fileId === null || filename === null || mimeType === null || sizeBytes === null || previewType === null || attachmentRevision === null || !isEpochMsValue(createdAtMs) || !isSoaiFilePreviewType(previewType)) {
        return null;
    }
    return { type: 'soai_file', attachmentId, fileId, filename, mimeType, sizeBytes, previewType, attachmentRevision, createdAtMs };
};

const normalizeSoaiFileStoragePart = (part: BackendMessageRecord): SoaiFileStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_FILE_FIELDS) || part['type'] !== 'soai_file') {
        return null;
    }
    const attachmentId = normalizeRequiredTextField(part, 'attachment_id', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const fileId = normalizeRequiredTextField(part, 'file_id', SOAI_ATTACHMENT_ID_MAX_LENGTH);
    const filename = normalizeRequiredTextField(part, 'filename', SOAI_FILE_NAME_MAX_LENGTH);
    const mimeType = normalizeRequiredTextField(part, 'mime_type', SOAI_FILE_MIME_TYPE_MAX_LENGTH);
    const sizeBytes = normalizeNonNegativeIntegerField(part, 'size_bytes');
    const previewType = normalizeRequiredTextField(part, 'preview_type', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const attachmentRevision = normalizeNonNegativeIntegerField(part, 'attachment_revision');
    const createdAtMs = part['created_at_ms'];
    if (attachmentId === null || fileId === null || filename === null || mimeType === null || sizeBytes === null || previewType === null || attachmentRevision === null || !isEpochMsValue(createdAtMs)) {
        return null;
    }
    if (!isSoaiFilePreviewType(previewType)) {
        return null;
    }
    return {
        type: 'soai_file',
        attachmentId: attachmentId,
        fileId: fileId,
        filename,
        mimeType: mimeType,
        sizeBytes: sizeBytes,
        previewType: previewType,
        attachmentRevision: attachmentRevision,
        createdAtMs: createdAtMs
    };
};

const soaiFileContentPartCandidateFromAttachment = (attachment: ChatAttachment): BackendMessageRecord => {
    return {
        type: 'soai_file',
        attachmentId: attachment.attachmentId,
        fileId: attachment.fileId,
        filename: attachment.name,
        mimeType: attachment.mimeType,
        sizeBytes: attachment.sizeBytes,
        previewType: attachment.previewType,
        attachmentRevision: attachment.attachmentRevision,
        createdAtMs: attachment.createdAtMs
    };
};

const buildSoaiFileContentPartFromAttachment = (attachment: ChatAttachment): SoaiFileStoragePart => {
    const candidate = soaiFileContentPartCandidateFromAttachment(attachment);
    const normalized = normalizeSoaiFileContentPart(candidate);
    if (normalized === null) {
        throw new Error('Ready attachment metadata is invalid.');
    }
    return normalized;
};

const serializeSoaiFileContentPart = (part: SoaiFileContentPartFields): JsonObject => ({
    type: 'soai_file',
    'attachment_id': part.attachmentId,
    'file_id': part.fileId,
    filename: part.filename,
    'mime_type': part.mimeType,
    'size_bytes': part.sizeBytes,
    'preview_type': part.previewType,
    'attachment_revision': part.attachmentRevision,
    'created_at_ms': part.createdAtMs
});

const isSoaiFileAttachmentReadyForSend = (attachment: ChatAttachment): boolean => {
    return normalizeSoaiFileContentPart(soaiFileContentPartCandidateFromAttachment(attachment)) !== null;
};

export { buildSoaiFileContentPartFromAttachment, isSoaiFileAttachmentReadyForSend, normalizeSoaiFileContentPart, normalizeSoaiFileStoragePart, serializeSoaiFileContentPart };
export type { SoaiFileStoragePart };
