/* SoAI - Chat SoAI path draft record parsing [frontend/assets/ts/features/chat/attachments/soaiPathDraftRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiLinkResolveRecord } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isPlainObject, isString } from '@core/typeGuards.ts';
import { cloneCanonicalSoaiPathContentPart, cloneSoaiPathStoragePart, mapSoaiPathContentPart, type SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { normalizeConversationVirtualPathValue } from '@features/chat/validation/soaiPathValues.ts';

interface SoaiPathDraftRecord {
    token: string;
    occurrenceIndex: number;
    displayLabel: string | null;
    contentPart: SoaiPathStoragePart;
}

type SoaiPathDraftMediaMetadata = { contentType: string | null; contentLength: number | null };

const requireRecordText = (record: JsonObject, fieldName: string): string => {
    const value = record[fieldName];
    if (!isString(value) || !value.trim()) {
        throw new Error(`SoAI path record ${fieldName} must be a non-empty string.`);
    }
    return value.trim();
};

const parseSoaiPathDraftRecord = (value: JsonValue | null | undefined): SoaiPathDraftRecord => {
    if (!isPlainObject(value)) {
        throw new Error('SoAI path draft record must be an object.');
    }
    const contentPart = value['content_part'];
    if (!isJsonObject(contentPart) || contentPart['type'] !== 'soai_path') {
        throw new Error('SoAI path draft record content_part must be a soai_path object.');
    }
    const occurrenceIndex = value['occurrence_index'];
    if (!isNonNegativeInteger(occurrenceIndex)) {
        throw new Error('SoAI path draft record occurrence_index must be a non-negative integer.');
    }
    const displayLabel = value['display_label'];
    if (displayLabel !== null && displayLabel !== undefined && !isString(displayLabel)) {
        throw new Error('SoAI path draft record display_label must be a string or null.');
    }
    return {
        token: requireRecordText(value, 'token'),
        occurrenceIndex,
        displayLabel: isString(displayLabel) && displayLabel.trim() ? displayLabel.trim() : null,
        contentPart: cloneCanonicalSoaiPathContentPart(contentPart)
    };
};

const mapSoaiPathResolveRecord = (record: SoaiLinkResolveRecord): SoaiPathDraftRecord => ({
    token: record.token,
    occurrenceIndex: record.occurrenceIndex,
    displayLabel: record.displayLabel,
    contentPart: mapSoaiPathContentPart(record.contentPart)
});

const parseSoaiPathDraftRecords = (values: ReadonlyArray<JsonValue | null | undefined>): SoaiPathDraftRecord[] => values.map(parseSoaiPathDraftRecord);

const serializeSoaiPathDraftRecord = (record: SoaiPathDraftRecord): JsonObject => ({
    type: 'soai_path_record',
    token: record.token,
    'occurrence_index': record.occurrenceIndex,
    'display_label': record.displayLabel,
    'content_part': serializeSoaiPathContentPart(record.contentPart)
});

const cloneSoaiPathDraftRecordContentPart = (record: SoaiPathDraftRecord): SoaiPathStoragePart => cloneSoaiPathStoragePart(record.contentPart);

const resolveSoaiPathDraftRecordTitle = (record: SoaiPathDraftRecord): string => record.displayLabel ?? record.contentPart.title;

const resolveSoaiPathDraftRecordToken = (record: SoaiPathDraftRecord): string => record.token;

const resolveSoaiPathDraftRecordPreviewType = (record: SoaiPathDraftRecord): string | null => record.contentPart.previewType;

const resolveSoaiPathDraftRecordRootFingerprint = (record: SoaiPathDraftRecord): string | null => record.contentPart.workspaceScope.rootFingerprint;

const resolveSoaiPathDraftRecordMediaMetadata = (record: SoaiPathDraftRecord): SoaiPathDraftMediaMetadata => ({
    contentType: record.contentPart.mimeType,
    contentLength: isNonNegativeInteger(record.contentPart.sizeBytes) ? record.contentPart.sizeBytes : null
});

const requireSoaiPathDraftRecordVirtualPath = (record: SoaiPathDraftRecord): string => {
    const canonicalValue = normalizeConversationVirtualPathValue(record.contentPart.sourceReference.value);
    if (canonicalValue === null) {
        throw new Error('SoAI path record source_reference.value must be canonical.');
    }
    return canonicalValue;
};

const isSoaiPathDraftRecord = (value: JsonValue | SoaiPathDraftRecord | null | undefined): value is SoaiPathDraftRecord => {
    if (!isPlainObject(value) || !isPlainObject(value['contentPart'])) {
        return false;
    }
    const contentPart = value['contentPart'];
    return isString(value['token']) && isNonNegativeInteger(value['occurrenceIndex']) && contentPart['type'] === 'soai_path';
};

export { cloneSoaiPathDraftRecordContentPart, isSoaiPathDraftRecord, mapSoaiPathResolveRecord, parseSoaiPathDraftRecord, parseSoaiPathDraftRecords, requireSoaiPathDraftRecordVirtualPath, resolveSoaiPathDraftRecordMediaMetadata, resolveSoaiPathDraftRecordPreviewType, resolveSoaiPathDraftRecordRootFingerprint, resolveSoaiPathDraftRecordTitle, resolveSoaiPathDraftRecordToken, serializeSoaiPathDraftRecord };
export type { SoaiPathDraftMediaMetadata, SoaiPathDraftRecord };
