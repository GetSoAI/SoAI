/* SoAI - Frontend settings backup V1 boundary [frontend/assets/ts/core/storage/persistence/settingsBackupSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeChatPreferences } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { serializeHardwareCache, serializePageControlStates } from '@core/storage/persistence/operationalPreferenceSerialization.ts';
import { serializeUiPreferences } from '@core/storage/persistence/uiPreferenceSerialization.ts';
import type { ChatPreferencesManager, HardwareCache, LogsCache, PageControlStates, UiPreferences } from '@core/storage/types.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

interface ExportedSettings {
    ui: JsonObject;
    chat: { preferences: JsonObject };
    logs: { 'line_limit': number; 'text_zoom': number };
    search: { recent: string[] };
    hardware: JsonObject;
    filters: { 'page_controls': JsonObject };
    'export_date': string;
}

interface SettingsBackupSource {
    ui: UiPreferences;
    chatPreferences: ChatPreferencesManager;
    logs: LogsCache;
    recentSearches: string[];
    hardware: HardwareCache;
    pageControls: PageControlStates;
    exportedAt: string;
}

interface ParsedSettingsBackup {
    ui: JsonObject | undefined;
    chatPreferences: JsonObject | undefined;
    logs: JsonObject | undefined;
    recentSearches: string[] | undefined;
    hardware: JsonObject | undefined;
    pageControls: JsonObject | undefined;
}

const SETTINGS_BACKUP_KEYS = new Set(['ui', 'chat', 'logs', 'search', 'hardware', 'filters', 'export_date']);

const readOptionalObject = (raw: JsonObject, key: string): JsonObject | undefined => {
    const value = raw[key];
    if (value === undefined) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`Settings backup ${key} must be an object`);
    return value;
};

const readOptionalRecentSearches = (raw: JsonObject): string[] | undefined => {
    const search = readOptionalObject(raw, 'search');
    if (!search || search['recent'] === undefined) return undefined;
    const recent = search['recent'];
    if (!isJsonArray(recent) || !recent.every(isString)) throw new TypeError('Settings backup search.recent must be a string array');
    return [...recent];
};

const serializeSettingsBackup = (source: SettingsBackupSource): ExportedSettings => ({
    ui: serializeUiPreferences(source.ui),
    chat: { preferences: serializeChatPreferences(source.chatPreferences) },
    logs: { 'line_limit': source.logs.lineLimit, 'text_zoom': source.logs.textZoom },
    search: { recent: [...source.recentSearches] },
    hardware: serializeHardwareCache(source.hardware),
    filters: { 'page_controls': serializePageControlStates(source.pageControls) },
    'export_date': source.exportedAt
});

const parseSettingsBackup = (value: JsonValue | null | undefined): ParsedSettingsBackup => {
    if (value === null || value === undefined) {
        return { ui: undefined, chatPreferences: undefined, logs: undefined, recentSearches: undefined, hardware: undefined, pageControls: undefined };
    }
    if (!isJsonObject(value)) throw new TypeError('Settings backup must be an object');
    for (const key of Object.keys(value)) {
        if (!SETTINGS_BACKUP_KEYS.has(key)) throw new Error('Unsupported exported settings payload key set.');
    }
    const exportDate = value['export_date'];
    if (exportDate !== undefined && !isString(exportDate)) throw new TypeError('Settings backup export_date must be a string');
    const chat = readOptionalObject(value, 'chat');
    const filters = readOptionalObject(value, 'filters');
    return {
        ui: readOptionalObject(value, 'ui'),
        chatPreferences: chat ? readOptionalObject(chat, 'preferences') : undefined,
        logs: readOptionalObject(value, 'logs'),
        recentSearches: readOptionalRecentSearches(value),
        hardware: readOptionalObject(value, 'hardware'),
        pageControls: filters ? readOptionalObject(filters, 'page_controls') : undefined
    };
};

export { parseSettingsBackup, serializeSettingsBackup };
export type { ExportedSettings, ParsedSettingsBackup, SettingsBackupSource };
