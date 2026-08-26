/* SoAI - WebUI chat preset record and envelope contracts [frontend/assets/ts/core/api/contracts/webuiChatPresetContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiChatPresetCreateRequest, WebuiChatPresetListResponse, WebuiChatPresetRecord, WebuiChatPresetRenameRequest, WebuiChatPresetReplaceRequest, WebuiChatPresetResetResponse } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { decodeChatPresetSections, serializeChatPresetSections } from '@core/api/contracts/webuiChatPresetSectionContracts.ts';
import { isUnicodeScalarText, trimPythonWhitespace } from '@core/primitives/text.ts';
import { EPOCH_MS_MIN, isEpochMsNumber } from '@core/time/epochMs.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';

const PRESET_ID_PATTERN = /^preset_[0-9a-f]{32}$/u;

const requireSafeInteger = (value: JsonValue | undefined, label: string, minimum: number): number => {
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum) throw new TypeError(`${label} must be a safe integer.`);
    return value;
};

const normalizePresetName = (value: JsonValue | undefined): string | null => {
    const normalized = typeof value === 'string' ? trimPythonWhitespace(value) : '';
    return normalized.length > 0 && Array.from(normalized).length <= 255 && isUnicodeScalarText(normalized) ? normalized : null;
};

const requirePresetName = (value: JsonValue | undefined): string => {
    const normalized = normalizePresetName(value);
    if (normalized === null) throw new TypeError('Chat preset name is invalid.');
    return normalized;
};

const isChatPresetNameValid = (value: string): boolean => normalizePresetName(value) !== null;

const requireCanonicalPresetName = (value: JsonValue | undefined): string => {
    if (typeof value !== 'string' || value.length === 0 || trimPythonWhitespace(value) !== value || Array.from(value).length > 255 || !isUnicodeScalarText(value)) {
        throw new TypeError('Chat preset name is invalid.');
    }
    return value;
};

const requirePresetId = (value: JsonValue | undefined): string => {
    if (typeof value !== 'string' || !PRESET_ID_PATTERN.test(value)) throw new TypeError('Chat preset id is invalid.');
    return value;
};

const serializeChatPresetPathId = (value: string): string => requirePresetId(value);

const serializeChatPresetDeleteQuery = (expectedRevision: number): ApiQueryParameters => ({
    'expected_revision': requireSafeInteger(expectedRevision, 'Chat preset expected revision', 1)
});

const decodeChatPresetRecord = (value: JsonValue): WebuiChatPresetRecord => {
    const record = requireRecord(value, 'Chat preset');
    assertExactRecordKeys(record, ['id', 'name', 'sections', 'revision', 'created_at_ms', 'modified_at_ms', 'omitted_settings_count', 'applicable'], 'Chat preset');
    const sections = decodeChatPresetSections(record['sections']);
    const createdAtMs = record['created_at_ms'];
    const modifiedAtMs = record['modified_at_ms'];
    if (typeof createdAtMs !== 'number' || !isEpochMsNumber(createdAtMs) || typeof modifiedAtMs !== 'number' || !isEpochMsNumber(modifiedAtMs) || modifiedAtMs < createdAtMs) throw new TypeError(`Chat preset timestamps must be bounded epoch values from ${String(EPOCH_MS_MIN)}.`);
    const applicable = record['applicable'];
    if (typeof applicable !== 'boolean' || applicable !== Object.keys(sections).length > 0) throw new TypeError('Chat preset applicability is invalid.');
    return {
        id: requirePresetId(record['id']),
        name: requireCanonicalPresetName(record['name']),
        sections,
        revision: requireSafeInteger(record['revision'], 'Chat preset revision', 1),
        createdAtMs,
        modifiedAtMs,
        omittedSettingsCount: requireSafeInteger(record['omitted_settings_count'], 'Chat preset omitted settings count', 0),
        applicable
    };
};

const decodeChatPresetListResponse = (value: JsonValue): WebuiChatPresetListResponse => {
    const record = requireRecord(value, 'Chat preset list');
    assertExactRecordKeys(record, ['presets', 'structurally_invalid_count'], 'Chat preset list');
    if (!Array.isArray(record['presets'])) throw new TypeError('Chat preset list.presets must be an array.');
    return {
        presets: record['presets'].map((preset) => decodeChatPresetRecord(preset)),
        structurallyInvalidCount: requireSafeInteger(record['structurally_invalid_count'], 'Chat preset structurally invalid count', 0)
    };
};

const serializeCreateFields = (name: string, sectionsValue: WebuiChatPresetCreateRequest['sections']): JsonObject => {
    const sections = serializeChatPresetSections(sectionsValue);
    if (Object.keys(sections).length === 0) throw new TypeError('Chat preset sections must be non-empty.');
    return { name: requirePresetName(name), sections };
};

const serializeChatPresetCreateRequest = (request: WebuiChatPresetCreateRequest): JsonObject => serializeCreateFields(request.name, request.sections);

const serializeChatPresetRenameRequest = (request: WebuiChatPresetRenameRequest): JsonObject => ({
    'expected_revision': requireSafeInteger(request.expectedRevision, 'Chat preset expected revision', 1),
    name: requirePresetName(request.name)
});

const serializeChatPresetReplaceRequest = (request: WebuiChatPresetReplaceRequest): JsonObject => ({
    'expected_revision': requireSafeInteger(request.expectedRevision, 'Chat preset expected revision', 1),
    ...serializeCreateFields(request.name, request.sections)
});

const decodeChatPresetResetResponse = (value: JsonValue): WebuiChatPresetResetResponse => {
    const record = requireRecord(value, 'Chat preset reset');
    assertExactRecordKeys(record, ['deleted'], 'Chat preset reset');
    return { deleted: requireSafeInteger(record['deleted'], 'Chat preset reset deleted count', 0) };
};

export { decodeChatPresetListResponse, decodeChatPresetRecord, decodeChatPresetResetResponse, isChatPresetNameValid, serializeChatPresetCreateRequest, serializeChatPresetDeleteQuery, serializeChatPresetPathId, serializeChatPresetRenameRequest, serializeChatPresetReplaceRequest };
export type { WebuiChatPresetCreateRequest, WebuiChatPresetListResponse, WebuiChatPresetRecord, WebuiChatPresetRenameRequest, WebuiChatPresetReplaceRequest, WebuiChatPresetResetResponse } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
