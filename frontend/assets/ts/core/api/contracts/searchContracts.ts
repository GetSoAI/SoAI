/* SoAI - Frontend global search response contracts [frontend/assets/ts/core/api/contracts/searchContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { decodeConversationSettingsAuthority, type ConversationSettingsAuthority } from '@core/chat/conversationSettingsAuthority.ts';
import { decodeConversationSource, type MessagingPlatform } from '@core/chat/conversationSource.ts';

interface SearchResultPluginResponse {
    name: string;
    displayName: string;
    versionSoaiplugin: string;
    state: string;
}

interface SearchResultModelResponse {
    universalId: string;
    displayName: string;
    plugin: string;
    state: string;
}

interface SearchResultDeviceResponse {
    type: string;
    name: string;
    id: number | string;
    component: string;
    identifier: string | null;
    extensions: JsonObject;
}

interface SearchResultConversationResponse {
    id: string;
    title: string;
    lastModifiedAtMs: number;
    color: string | null;
    isFavorite: boolean;
    isAutomation: boolean;
    isMessaging: boolean;
    messagingPlatform: MessagingPlatform | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
    settingsAuthority: ConversationSettingsAuthority;
}

interface SearchResultPromptResponse {
    id: string;
    name: string;
    modifiedAtMs: number;
    color: string | null;
}

interface SearchResultsResponse {
    plugins: SearchResultPluginResponse[];
    models: SearchResultModelResponse[];
    devices: SearchResultDeviceResponse[];
    conversations: SearchResultConversationResponse[];
    prompts: SearchResultPromptResponse[];
}

const readRequiredId = (value: JsonValue | undefined, label: string): number | string => {
    if (typeof value === 'number' && Number.isInteger(value)) return value;
    return readRequiredTrimmedString({ entry: value }, 'entry', label);
};

const readRecordArray = (value: JsonValue | undefined, label: string): JsonValue[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return [...value];
};

const decodePlugin = (value: JsonValue, label: string): SearchResultPluginResponse => {
    const record = requireRecord(value, label);
    return {
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        displayName: readRequiredTrimmedString(record, 'display_name', `${label}.display_name`),
        versionSoaiplugin: readRequiredTrimmedString(record, 'version_soaiplugin', `${label}.version_soaiplugin`),
        state: readRequiredTrimmedString(record, 'state', `${label}.state`)
    };
};

const decodeModel = (value: JsonValue, label: string): SearchResultModelResponse => {
    const record = requireRecord(value, label);
    return {
        universalId: readRequiredTrimmedString(record, 'universal_id', `${label}.universal_id`),
        displayName: readRequiredTrimmedString(record, 'display_name', `${label}.display_name`),
        plugin: readRequiredTrimmedString(record, 'plugin', `${label}.plugin`),
        state: readRequiredTrimmedString(record, 'state', `${label}.state`)
    };
};

const decodeDevice = (value: JsonValue, label: string): SearchResultDeviceResponse => {
    const record = requireRecord(value, label);
    const knownFields = new Set(['type', 'name', 'id', 'component', 'identifier']);
    const extensions: JsonObject = {};
    for (const [key, extensionValue] of Object.entries(record)) {
        if (!knownFields.has(key)) extensions[key] = extensionValue;
    }
    const identifier = record['identifier'];
    return {
        type: readRequiredTrimmedString(record, 'type', `${label}.type`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        id: readRequiredId(record['id'], `${label}.id`),
        component: readRequiredTrimmedString(record, 'component', `${label}.component`),
        identifier: identifier === null || identifier === undefined ? null : readRequiredTrimmedString(record, 'identifier', `${label}.identifier`),
        extensions
    };
};

const decodeConversation = (value: JsonValue, label: string): SearchResultConversationResponse => {
    const record = requireRecord(value, label);
    const source = decodeConversationSource(record, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        title: readRequiredTrimmedString(record, 'title', `${label}.title`),
        lastModifiedAtMs: readRequiredNonNegativeIntegerValue(record['last_modified_at_ms'], `${label}.last_modified_at_ms`),
        color: record['color'] === null || record['color'] === undefined ? null : readRequiredStringValue(record['color'], `${label}.color`),
        isFavorite: record['is_favorite'] === undefined ? false : readRequiredBooleanValue(record['is_favorite'], `${label}.is_favorite`),
        isAutomation: readRequiredBooleanValue(record['is_automation'], `${label}.is_automation`),
        ...source,
        settingsAuthority: decodeConversationSettingsAuthority(record['settings_authority'], `${label}.settings_authority`)
    };
};

const decodePrompt = (value: JsonValue, label: string): SearchResultPromptResponse => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        modifiedAtMs: readRequiredNonNegativeIntegerValue(record['modified_at_ms'], `${label}.modified_at_ms`),
        color: record['color'] === null || record['color'] === undefined ? null : readRequiredStringValue(record['color'], `${label}.color`)
    };
};

const decodeSearchResults = (value: ApiResponsePayload): SearchResultsResponse => {
    const record = requireRecord(value, 'Search results response');
    return {
        plugins: readRecordArray(record['plugins'], 'Search results response.plugins').map((entry, index) => decodePlugin(entry, `Search results response.plugins[${String(index)}]`)),
        models: readRecordArray(record['models'], 'Search results response.models').map((entry, index) => decodeModel(entry, `Search results response.models[${String(index)}]`)),
        devices: readRecordArray(record['devices'], 'Search results response.devices').map((entry, index) => decodeDevice(entry, `Search results response.devices[${String(index)}]`)),
        conversations: readRecordArray(record['conversations'], 'Search results response.conversations').map((entry, index) => decodeConversation(entry, `Search results response.conversations[${String(index)}]`)),
        prompts: readRecordArray(record['prompts'], 'Search results response.prompts').map((entry, index) => decodePrompt(entry, `Search results response.prompts[${String(index)}]`))
    };
};

export { decodeSearchResults };
export type { SearchResultConversationResponse, SearchResultDeviceResponse, SearchResultModelResponse, SearchResultPluginResponse, SearchResultPromptResponse, SearchResultsResponse };
