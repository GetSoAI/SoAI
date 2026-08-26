/* SoAI - Frontend storage group persistence serialization [frontend/assets/ts/core/storage/persistence/storageGroupSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeChatCache } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { serializeFiltersCache, serializeHardwareCache } from '@core/storage/persistence/operationalPreferenceSerialization.ts';
import { serializeUiPreferences } from '@core/storage/persistence/uiPreferenceSerialization.ts';
import type { StorageCache, SyncGroup } from '@core/storage/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeStorageGroup = (cache: StorageCache, group: SyncGroup): JsonObject => {
    if (group === 'ui') return serializeUiPreferences(cache.ui);
    if (group === 'chat') return serializeChatCache(cache.chat);
    if (group === 'logs') return { 'line_limit': cache.logs.lineLimit, 'text_zoom': cache.logs.textZoom };
    if (group === 'terminal') return { 'text_zoom': cache.terminal.textZoom };
    if (group === 'search') return { recent: cache.search.recent };
    if (group === 'hardware') return serializeHardwareCache(cache.hardware);
    if (group === 'filters') return serializeFiltersCache(cache.filters);
    if (group === 'wizard') return { completed: cache.wizard.completed };
    return { 'advanced_mode': cache.settings.advancedMode };
};

const serializeStorageCache = (cache: StorageCache, groups: ReadonlySet<SyncGroup>): JsonObject => {
    const serialized: JsonObject = {};
    for (const group of groups) serialized[group] = serializeStorageGroup(cache, group);
    serialized['misc'] = cache.misc;
    return serialized;
};

export { serializeStorageCache, serializeStorageGroup };
