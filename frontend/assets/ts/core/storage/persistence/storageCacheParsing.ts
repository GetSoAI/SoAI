/* SoAI - Frontend storage cache boundary parsing [frontend/assets/ts/core/storage/persistence/storageCacheParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN } from '@core/chat/parameters/textZoom.ts';
import { writeClockPreferenceState, readClockPreferenceState } from '@core/storage/clockPreferences.ts';
import { applyChatPatch } from '@core/storage/persistence/mergeremotepreferences/actions.ts';
import { applyHardwarePatch, applyLogsPatch, applySearchPatch, applySettingsPatch, applyTerminalPatch, applyWizardPatch, mergeMisc } from '@core/storage/persistence/mergeremotepreferences/adapters.ts';
import { applyUiPatch } from '@core/storage/persistence/mergeremotepreferences/mappers.ts';
import { applyPageControlStatesPatch } from '@core/storage/service/pageControlMappers.ts';
import type { StorageCache } from '@core/storage/types.ts';
import { isArray, isNumber, isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface StorageCacheParsingDependencies {
    clone: <Value>(value: Value) => Value;
    createDefaults: () => StorageCache;
    internalRemoteKeys: ReadonlySet<string>;
    normalizeLimit: (limit: number) => number;
    normalizeZoom: (zoom: number, minimum: number, maximum: number) => number;
    preserveDefaultMisc: boolean;
    rejectUnknownKeys: boolean;
}

const SUPPORTED_STORAGE_CACHE_KEYS = new Set(['ui', 'chat', 'logs', 'terminal', 'search', 'hardware', 'filters', 'wizard', 'settings', 'misc']);

const assertSupportedStorageCachePayload = (raw: JsonObject): void => {
    for (const key of Object.keys(raw)) {
        if (!SUPPORTED_STORAGE_CACHE_KEYS.has(key)) {
            throw new Error('Unsupported storage cache payload key set.');
        }
    }
};

const parseStorageCache = (raw: JsonValue | null | undefined, dependencies: StorageCacheParsingDependencies): StorageCache => {
    if (!isJsonObject(raw)) {
        throw new Error('Storage cache payload must be an object');
    }
    if (dependencies.rejectUnknownKeys) {
        assertSupportedStorageCachePayload(raw);
    }

    const defaults = dependencies.createDefaults();
    const cache = dependencies.clone(defaults);
    applyUiPatch(raw['ui'], cache.ui);
    cache.ui.headerAutoHide = cache.ui.headerAutoHide !== false;
    cache.ui.showScrollToTopButton = cache.ui.showScrollToTopButton !== false;
    cache.ui.glassEnabled = cache.ui.glassEnabled !== false;
    writeClockPreferenceState(cache.ui, readClockPreferenceState(cache.ui));
    if (!isObject(cache.ui.modalStates) || isArray(cache.ui.modalStates)) {
        cache.ui.modalStates = {};
    }
    if (!isNumber(cache.ui.mainStatePreferenceVersion) || !Number.isFinite(cache.ui.mainStatePreferenceVersion)) {
        cache.ui.mainStatePreferenceVersion = 0;
    }

    applyChatPatch(raw['chat'], cache.chat, defaults.chat);
    applyLogsPatch(raw['logs'], cache.logs);
    applySearchPatch(raw['search'], cache.search);
    applyTerminalPatch(raw['terminal'], cache.terminal);
    applyHardwarePatch(raw['hardware'], cache.hardware, { clone: dependencies.clone });
    if (!isObject(cache.hardware.gpuSettings) || isArray(cache.hardware.gpuSettings)) {
        cache.hardware.gpuSettings = {};
    }

    const filters = raw['filters'];
    if (isObject(filters)) {
        applyPageControlStatesPatch(filters['page_controls'], cache.filters.pageControls);
    }
    applyWizardPatch(raw['wizard'], cache.wizard);
    applySettingsPatch(raw['settings'], cache.settings);

    cache.chat.textZoom = dependencies.normalizeZoom(cache.chat.textZoom, CHAT_TEXT_ZOOM_MIN, CHAT_TEXT_ZOOM_MAX);
    cache.logs.lineLimit = dependencies.normalizeLimit(cache.logs.lineLimit);
    cache.logs.textZoom = dependencies.normalizeZoom(cache.logs.textZoom, 0.5, 2);
    cache.terminal.textZoom = dependencies.normalizeZoom(cache.terminal.textZoom, 0.5, 2);
    cache.misc = dependencies.clone(
        mergeMisc(raw, {
            defaultsMisc: dependencies.preserveDefaultMisc ? defaults.misc : {},
            internalRemoteKeys: dependencies.internalRemoteKeys
        })
    );
    return cache;
};

export { parseStorageCache };
export type { StorageCacheParsingDependencies };
