/* SoAI - Canonical soai_path attachment content part contracts [frontend/assets/ts/features/chat/attachments/soaiPathContentPart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsValue } from '@core/time/epochMs.ts';
import type { SoaiPathContentPart } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isPlainObject, isString } from '@core/typeGuards.ts';
import { hasOnlyFields, normalizeOptionalNonNegativeIntegerField, normalizeRequiredTextField, SOAI_FILE_NAME_MAX_LENGTH, SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH, type BackendMessageRecord } from '@features/chat/attachments/attachmentContentFieldValidation.ts';
import { isSoaiPathPreviewType, type SoaiPathPreviewType } from '@features/chat/attachments/attachmentPreviewTypes.ts';
import { normalizeConversationVirtualPathValue, normalizeWorkspaceRelativePathValue } from '@features/chat/validation/soaiPathValues.ts';

interface SoaiPathStoragePart extends SoaiPathContentPart {
    previewType: SoaiPathPreviewType;
}

const SHA256_FINGERPRINT_LENGTH = 71;
const SOAI_PATH_FIELDS = new Set(['type', 'entry_type', 'source_reference', 'tool_reference', 'workspace_scope', 'target_fingerprint', 'title', 'preview_type', 'mime_type', 'size_bytes', 'modified_at_ms', 'resolved_at_ms']);
const SOAI_PATH_DOMAIN_FIELDS = new Set(['type', 'entryType', 'sourceReference', 'toolReference', 'workspaceScope', 'targetFingerprint', 'title', 'previewType', 'mimeType', 'sizeBytes', 'modifiedAtMs', 'resolvedAtMs']);
const SOAI_PATH_SOURCE_REFERENCE_FIELDS = new Set(['type', 'value']);
const SOAI_PATH_TOOL_REFERENCE_FIELDS = new Set(['type', 'value']);
const SOAI_PATH_WORKSPACE_SCOPE_FIELDS = new Set(['type', 'root_fingerprint']);
const SOAI_PATH_DOMAIN_WORKSPACE_SCOPE_FIELDS = new Set(['type', 'rootFingerprint']);
const SOAI_PATH_TARGET_FINGERPRINT_FIELDS = new Set(['type', 'value']);

const normalizeSha256Fingerprint = (value: JsonValue | null | undefined): string | null => {
    if (!isString(value) || value.trim() !== value || value.length !== SHA256_FINGERPRINT_LENGTH || !value.startsWith('sha256:')) {
        return null;
    }
    const digest = value.slice('sha256:'.length);
    return /^[a-f0-9]{64}$/.test(digest) ? value : null;
};

const normalizeSoaiPathStoragePart = (part: BackendMessageRecord): SoaiPathStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_PATH_FIELDS) || part['type'] !== 'soai_path') {
        return null;
    }
    const title = normalizeRequiredTextField(part, 'title', SOAI_FILE_NAME_MAX_LENGTH);
    const entryType = normalizeRequiredTextField(part, 'entry_type', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const previewType = normalizeRequiredTextField(part, 'preview_type', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const sourceReference = part['source_reference'];
    const toolReference = part['tool_reference'];
    const workspaceScope = part['workspace_scope'];
    const targetFingerprint = part['target_fingerprint'];
    const sizeBytes = normalizeOptionalNonNegativeIntegerField(part, 'size_bytes');
    const modifiedAtMs = part['modified_at_ms'];
    const resolvedAtMs = part['resolved_at_ms'];
    const sourceReferenceValue = isPlainObject(sourceReference) && hasOnlyFields(sourceReference, SOAI_PATH_SOURCE_REFERENCE_FIELDS) && sourceReference['type'] === 'conversation_virtual_path' ? normalizeConversationVirtualPathValue(sourceReference['value']) : null;
    const toolReferenceValue = isPlainObject(toolReference) && hasOnlyFields(toolReference, SOAI_PATH_TOOL_REFERENCE_FIELDS) && toolReference['type'] === 'workspace_relative_path' ? normalizeWorkspaceRelativePathValue(toolReference['value']) : null;
    const rootFingerprint = isPlainObject(workspaceScope) && hasOnlyFields(workspaceScope, SOAI_PATH_WORKSPACE_SCOPE_FIELDS) && workspaceScope['type'] === 'conversation_effective_workspace' ? normalizeSha256Fingerprint(workspaceScope['root_fingerprint']) : null;
    if (entryType !== 'file' && entryType !== 'folder') {
        return null;
    }
    if (previewType === null || !isSoaiPathPreviewType(previewType)) {
        return null;
    }
    const expectedFingerprintType = entryType === 'file' ? 'file_sha256' : 'folder_listing_sha256';
    const targetFingerprintValue = isPlainObject(targetFingerprint) && hasOnlyFields(targetFingerprint, SOAI_PATH_TARGET_FINGERPRINT_FIELDS) && targetFingerprint['type'] === expectedFingerprintType ? normalizeSha256Fingerprint(targetFingerprint['value']) : null;
    if (title === null || part['size_bytes'] === undefined || sizeBytes === undefined || (entryType === 'file' && sizeBytes === null) || sourceReferenceValue === null || toolReferenceValue === null || rootFingerprint === null || targetFingerprintValue === null || !isEpochMsValue(modifiedAtMs) || !isEpochMsValue(resolvedAtMs)) {
        return null;
    }
    const mimeType = part['mime_type'];
    if (mimeType === undefined) {
        return null;
    }
    if (mimeType !== null && mimeType !== undefined && (!isString(mimeType) || !mimeType.trim())) {
        return null;
    }
    return {
        type: 'soai_path',
        entryType: entryType,
        sourceReference: { type: 'conversation_virtual_path', value: sourceReferenceValue },
        toolReference: { type: 'workspace_relative_path', value: toolReferenceValue },
        workspaceScope: { type: 'conversation_effective_workspace', rootFingerprint: rootFingerprint },
        targetFingerprint: { type: expectedFingerprintType, value: targetFingerprintValue },
        title,
        previewType: previewType,
        mimeType: isString(mimeType) ? mimeType.trim() : null,
        sizeBytes: sizeBytes,
        modifiedAtMs: modifiedAtMs,
        resolvedAtMs: resolvedAtMs
    };
};

const normalizeSoaiPathContentPart = (part: BackendMessageRecord): SoaiPathStoragePart | null => {
    if (!hasOnlyFields(part, SOAI_PATH_DOMAIN_FIELDS) || part['type'] !== 'soai_path') {
        return null;
    }
    const entryType = normalizeRequiredTextField(part, 'entryType', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const previewType = normalizeRequiredTextField(part, 'previewType', SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH);
    const title = normalizeRequiredTextField(part, 'title', SOAI_FILE_NAME_MAX_LENGTH);
    const sourceReference = part['sourceReference'];
    const toolReference = part['toolReference'];
    const workspaceScope = part['workspaceScope'];
    const targetFingerprint = part['targetFingerprint'];
    const sizeBytes = normalizeOptionalNonNegativeIntegerField(part, 'sizeBytes');
    const modifiedAtMs = part['modifiedAtMs'];
    const resolvedAtMs = part['resolvedAtMs'];
    const sourceReferenceValue = isPlainObject(sourceReference) && hasOnlyFields(sourceReference, SOAI_PATH_SOURCE_REFERENCE_FIELDS) && sourceReference['type'] === 'conversation_virtual_path' ? normalizeConversationVirtualPathValue(sourceReference['value']) : null;
    const toolReferenceValue = isPlainObject(toolReference) && hasOnlyFields(toolReference, SOAI_PATH_TOOL_REFERENCE_FIELDS) && toolReference['type'] === 'workspace_relative_path' ? normalizeWorkspaceRelativePathValue(toolReference['value']) : null;
    const rootFingerprint = isPlainObject(workspaceScope) && hasOnlyFields(workspaceScope, SOAI_PATH_DOMAIN_WORKSPACE_SCOPE_FIELDS) && workspaceScope['type'] === 'conversation_effective_workspace' ? normalizeSha256Fingerprint(workspaceScope['rootFingerprint']) : null;
    if (entryType !== 'file' && entryType !== 'folder') return null;
    if (previewType === null || !isSoaiPathPreviewType(previewType)) return null;
    const expectedFingerprintType = entryType === 'file' ? 'file_sha256' : 'folder_listing_sha256';
    const targetFingerprintValue = isPlainObject(targetFingerprint) && hasOnlyFields(targetFingerprint, SOAI_PATH_TARGET_FINGERPRINT_FIELDS) && targetFingerprint['type'] === expectedFingerprintType ? normalizeSha256Fingerprint(targetFingerprint['value']) : null;
    const mimeType = part['mimeType'];
    if (title === null || part['sizeBytes'] === undefined || sizeBytes === undefined || (entryType === 'file' && sizeBytes === null) || sourceReferenceValue === null || toolReferenceValue === null || rootFingerprint === null || targetFingerprintValue === null || !isEpochMsValue(modifiedAtMs) || !isEpochMsValue(resolvedAtMs) || mimeType === undefined || (mimeType !== null && (!isString(mimeType) || !mimeType.trim()))) {
        return null;
    }
    return {
        type: 'soai_path',
        entryType,
        sourceReference: { type: 'conversation_virtual_path', value: sourceReferenceValue },
        toolReference: { type: 'workspace_relative_path', value: toolReferenceValue },
        workspaceScope: { type: 'conversation_effective_workspace', rootFingerprint },
        targetFingerprint: { type: expectedFingerprintType, value: targetFingerprintValue },
        title,
        previewType,
        mimeType: isString(mimeType) ? mimeType.trim() : null,
        sizeBytes,
        modifiedAtMs,
        resolvedAtMs
    };
};

const mapSoaiPathContentPart = (part: SoaiPathContentPart): SoaiPathStoragePart => {
    const normalized = normalizeSoaiPathContentPart({
        type: part.type,
        entryType: part.entryType,
        sourceReference: { type: part.sourceReference.type, value: part.sourceReference.value },
        toolReference: { type: part.toolReference.type, value: part.toolReference.value },
        workspaceScope: { type: part.workspaceScope.type, rootFingerprint: part.workspaceScope.rootFingerprint },
        targetFingerprint: { type: part.targetFingerprint.type, value: part.targetFingerprint.value },
        title: part.title,
        previewType: part.previewType,
        mimeType: part.mimeType,
        sizeBytes: part.sizeBytes,
        modifiedAtMs: part.modifiedAtMs,
        resolvedAtMs: part.resolvedAtMs
    });
    if (normalized === null) {
        throw new Error('SoAI path response content part is invalid.');
    }
    return normalized;
};

const cloneCanonicalSoaiPathContentPart = (part: BackendMessageRecord): SoaiPathStoragePart => {
    const normalized = normalizeSoaiPathStoragePart(part);
    if (!isPlainObject(normalized)) {
        throw new Error('SoAI path content part is invalid.');
    }
    return normalized;
};

const cloneSoaiPathStoragePart = (part: SoaiPathStoragePart): SoaiPathStoragePart => ({
    type: part.type,
    entryType: part.entryType,
    sourceReference: { ...part.sourceReference },
    toolReference: { ...part.toolReference },
    workspaceScope: { ...part.workspaceScope },
    targetFingerprint: { ...part.targetFingerprint },
    title: part.title,
    previewType: part.previewType,
    mimeType: part.mimeType,
    sizeBytes: part.sizeBytes,
    modifiedAtMs: part.modifiedAtMs,
    resolvedAtMs: part.resolvedAtMs
});

export { cloneCanonicalSoaiPathContentPart, cloneSoaiPathStoragePart, mapSoaiPathContentPart, normalizeSoaiPathContentPart, normalizeSoaiPathStoragePart };
export type { SoaiPathStoragePart };
